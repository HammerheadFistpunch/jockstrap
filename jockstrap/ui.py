"""Native desktop workspace for manually authored microwave networks."""
from dataclasses import asdict
import copy
from concurrent.futures import Future
import json
from pathlib import Path
import tkinter as tk
import threading
from tkinter import filedialog, messagebox, simpledialog, ttk

from .equipment import PRESETS, make_radio
from .project import Project, Radio, Site, Link
from .terrain import GEOD


class EditDialog(tk.Toplevel):
    def __init__(self, owner, title, fields, values, on_save, preset_callback=None):
        super().__init__(owner)
        self.title(title)
        self.transient(owner)
        self.geometry("600x650")
        self.variables = {}
        self.on_save = on_save
        canvas = tk.Canvas(self, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        form = ttk.Frame(canvas, padding=15)
        window = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        form.columnconfigure(1, weight=1)
        for row, (key, label, choices) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
            var = tk.StringVar(value=str(values.get(key, "") if values.get(key) is not None else ""))
            self.variables[key] = var
            control = ttk.Combobox(form, textvariable=var, values=choices, state="readonly") if choices else ttk.Entry(form, textvariable=var)
            control.grid(row=row, column=1, sticky="ew", pady=5)
            if key == "equipment" and preset_callback:
                control.bind("<<ComboboxSelected>>", lambda event: preset_callback(self.variables))
        ttk.Label(form, text="Power and receiver threshold are planning assumptions. Set values for the intended bandwidth and modulation. Peer aiming applies only to a single link.", wraplength=530).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=12)
        ttk.Button(form, text="Save", command=self.save).grid(row=len(fields)+1, column=1, sticky="e")
        self.grab_set()

    def save(self):
        try:
            self.on_save({key: var.get() for key, var in self.variables.items()})
            self.destroy()
        except (ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("Check inputs", str(exc), parent=self)


class Planner(tk.Tk):
    def __init__(self, project=None, path=None, usgs=False, model="knife-edge"):
        super().__init__()
        self.project = project or Project()
        self.path = Path(path) if path else None
        self.results = {}
        self.revision = 0
        self.dirty = False
        self.future = None
        self.title("Jockstrap — Microwave network planner")
        self.geometry("1400x900")
        self.minsize(1100, 750)
        self.protocol("WM_DELETE_WINDOW", self.close)
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        for text, command in (("New", self.new), ("Open", self.open), ("Save", self.save),
                              ("Save as", lambda: self.save(True)), ("Add site", self.add_site),
                              ("Add radio", self.add_radio), ("Connect radios", self.add_link),
                              ("Select DEM", self.select_dem), ("Analyze network", self.analyze)):
            ttk.Button(toolbar, text=text, command=command).pack(side="left", padx=2)
        self.usgs = tk.BooleanVar(value=usgs)
        ttk.Checkbutton(toolbar, text="USGS terrain", variable=self.usgs, command=self.changed).pack(side="left", padx=6)
        self.model = tk.StringVar(value=model)
        model_box = ttk.Combobox(toolbar, textvariable=self.model, values=("knife-edge", "itm"), state="readonly", width=12)
        model_box.pack(side="left")
        model_box.bind("<<ComboboxSelected>>", lambda event: self.changed())
        ttk.Button(toolbar, text="Path settings", command=self.path_settings).pack(side="left", padx=4)
        self.status = tk.StringVar(value="Add sites on the map, add radios, then connect them. Analyze without terrain gives provisional free-space results.")
        ttk.Label(self, textvariable=self.status, padding=8, wraplength=1300).pack(fill="x")
        split = ttk.Panedwindow(self, orient="horizontal")
        split.pack(fill="both", expand=True)
        sidebar = ttk.Frame(split, padding=6)
        map_frame = ttk.Frame(split)
        split.add(sidebar, weight=1)
        split.add(map_frame, weight=3)
        self.sites_table = self.table(sidebar, "Sites", ("Location",), self.edit_site, self.delete_site)
        self.radios_table = self.table(sidebar, "Radios / antennas", ("Site", "Role", "Equipment"), self.edit_radio, self.delete_radio)
        self.links_table = self.table(sidebar, "Wireless links", ("Status", "A → B dBm", "B → A dBm"), self.inspect_link, self.delete_link)
        ttk.Button(sidebar, text="Edit selected link", command=self.edit_link).pack(fill="x", pady=3)
        ttk.Button(sidebar, text="Export analysis JSON", command=self.export).pack(fill="x", pady=3)
        self.details = tk.Text(sidebar, height=8, wrap="word", state="disabled")
        self.details.pack(fill="both", expand=True, pady=6)
        self.links_table.bind("<<TreeviewSelect>>", self.show_summary)
        try:
            from tkintermapview import TkinterMapView
            self.map = TkinterMapView(map_frame, corner_radius=0)
            self.map.pack(fill="both", expand=True)
            self.map.set_position(40.57, -111.86)
            self.map.set_zoom(10)
            self.map.add_right_click_menu_command(label="Add site here", command=self.add_site, pass_coords=True)
        except Exception as exc:
            self.map = None
            ttk.Label(map_frame, text=f"Map unavailable: {exc}\nYou can still enter coordinates and analyze links.", wraplength=650).pack(padx=30, pady=30)
        ttk.Label(map_frame, text="Right-click map to add a site. Wedges indicate antenna direction, not predicted coverage. Basemap requires Internet; local DEM analysis works offline.", wraplength=900, padding=8).pack(fill="x")
        self.refresh()
        self.after(150, self.poll)

    def table(self, parent, title, columns, edit, delete):
        ttk.Label(parent, text=title).pack(anchor="w", pady=(8, 2))
        tree = ttk.Treeview(parent, columns=columns, height=4, selectmode="browse")
        tree.heading("#0", text="Name")
        tree.column("#0", width=125)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=110)
        tree.pack(fill="x")
        tree.bind("<Double-1>", lambda event: edit())
        buttons = ttk.Frame(parent)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Edit / inspect", command=edit).pack(side="left")
        ttk.Button(buttons, text="Delete", command=delete).pack(side="right")
        return tree

    def selected(self, table, objects):
        selected = table.selection()
        return next((obj for obj in objects if selected and obj.id == selected[0]), None)

    def apply(self, candidate):
        candidate.validate()
        self.project = candidate
        self.changed()

    def changed(self):
        self.revision += 1
        self.dirty = True
        self.results.clear()
        self.status.set("Project changed. Recalculate links to update signal estimates.")
        self.refresh()

    def add_site(self, coords=None):
        site = Site(f"Site {len(self.project.sites)+1}", *(coords or (40.57, -111.86)))
        self.site_dialog(site, False)

    def edit_site(self):
        site = self.selected(self.sites_table, self.project.sites)
        if site:
            self.site_dialog(site, True)

    def site_dialog(self, site, existing):
        def save(values):
            candidate = copy.deepcopy(self.project)
            obj = Site(values['name'], float(values['lat']), float(values['lon']), id=site.id)
            candidate.sites = [obj if s.id == site.id else s for s in candidate.sites] if existing else [*candidate.sites, obj]
            self.apply(candidate)
            if self.map:
                self.map.set_position(obj.lat, obj.lon)
        EditDialog(self, "Site location", [("name", "Name", None), ("lat", "Latitude", None), ("lon", "Longitude", None)], asdict(site), save)

    def add_radio(self):
        site = self.selected(self.sites_table, self.project.sites)
        if site is None:
            messagebox.showinfo("Select a site", "Select the site that will host this radio.", parent=self)
            return
        self.radio_dialog(make_radio(site.id, "Generic sector" if not self.project.radios else "Generic client dish"), False)

    def edit_radio(self):
        radio = self.selected(self.radios_table, self.project.radios)
        if radio:
            self.radio_dialog(radio, True)

    def radio_dialog(self, radio, existing):
        fields = [("name", "Radio name", None), ("equipment", "Equipment preset", tuple(PRESETS)),
                  ("role", "Role", ("sector", "client", "ptp")), ("protocol", "Protocol family", ("custom", "airmax-ac", "ltu", "wifi-ax", "epmp", "omada-bridge", "pharos-ac")),
                  ("frequency_ghz", "Frequency (GHz)", None), ("channel_width_mhz", "Channel width (MHz)", None),
                  ("height_m", "Height above terrain (m)", None), ("tx_power_dbm", "TX power per channel (dBm)", None),
                  ("rx_threshold_dbm", "RX threshold for target mode (dBm)", None), ("gain_dbi", "Antenna gain (dBi)", None),
                  ("az_beamwidth_deg", "Horizontal beamwidth (°)", None), ("el_beamwidth_deg", "Vertical beamwidth (°)", None),
                  ("pattern_floor_db", "Off-axis loss cap (dB)", None), ("polarization", "Polarization", ("horizontal", "vertical", "dual")),
                  ("feeder_loss_db", "Feeder loss (dB)", None), ("aim", "Aim", ("fixed", "peer")),
                  ("azimuth_deg", "Azimuth: true north 0°, east 90°", None), ("tilt_deg", "Tilt: positive up (°)", None),
                  ("max_clients", "Max clients (blank = unspecified)", None), ("assumptions", "Equipment notes", None)]
        def preset(variables):
            name = variables['equipment'].get()
            new = asdict(make_radio(radio.site_id, name))
            for key in ("role", "protocol", "gain_dbi", "az_beamwidth_deg", "el_beamwidth_deg", "aim", "max_clients", "assumptions"):
                variables[key].set("" if new[key] is None else str(new[key]))
        def save(values):
            candidate = copy.deepcopy(self.project)
            numbers = {key for key, _, choices in fields if choices is None} - {"name", "assumptions", "max_clients"}
            for key in numbers:
                values[key] = float(values[key])
            values['max_clients'] = int(values['max_clients']) if values['max_clients'].strip() else None
            obj = Radio(site_id=radio.site_id, id=radio.id, **values)
            candidate.radios = [obj if r.id == radio.id else r for r in candidate.radios] if existing else [*candidate.radios, obj]
            self.apply(candidate)
        EditDialog(self, "Radio and antenna properties", fields, asdict(radio), save, preset)

    def add_link(self):
        if len(self.project.radios) < 2:
            messagebox.showinfo("Add radios", "Add radios at two different sites first.", parent=self)
            return
        self.link_dialog(Link(f"Link {len(self.project.links)+1}", self.project.radios[0].id, self.project.radios[1].id), False)

    def edit_link(self):
        link = self.selected(self.links_table, self.project.links)
        if link:
            self.link_dialog(link, True)

    def link_dialog(self, link, existing):
        sites = {s.id: s for s in self.project.sites}
        labels = {f"{sites[r.site_id].name} / {r.name} [{r.id[:6]}]": r.id for r in self.project.radios}
        reverse = {value: key for key, value in labels.items()}
        values = dict(name=link.name, a=reverse[link.a_radio_id], b=reverse[link.b_radio_id], reserve_db=link.reserve_db, extra_loss_db=link.extra_loss_db)
        def save(values):
            candidate = copy.deepcopy(self.project)
            obj = Link(values['name'], labels[values['a']], labels[values['b']], float(values['reserve_db']), float(values['extra_loss_db']), id=link.id)
            candidate.links = [obj if l.id == link.id else l for l in candidate.links] if existing else [*candidate.links, obj]
            self.apply(candidate)
        EditDialog(self, "Connect two radios", [("name", "Link name", None), ("a", "Radio A", tuple(labels)), ("b", "Radio B", tuple(labels)), ("reserve_db", "Required reserve (dB)", None), ("extra_loss_db", "Additional combined loss (dB)", None)], values, save)

    def delete_site(self):
        site = self.selected(self.sites_table, self.project.sites)
        if site and messagebox.askyesno("Delete site", "Delete this site, its radios, and their links?", parent=self):
            removed = {r.id for r in self.project.radios if r.site_id == site.id}
            self.project.sites = [s for s in self.project.sites if s.id != site.id]
            self.project.radios = [r for r in self.project.radios if r.id not in removed]
            self.project.links = [l for l in self.project.links if not removed.intersection((l.a_radio_id, l.b_radio_id))]
            self.changed()

    def delete_radio(self):
        radio = self.selected(self.radios_table, self.project.radios)
        if radio and messagebox.askyesno("Delete radio", "Delete this radio and its links?", parent=self):
            self.project.radios = [r for r in self.project.radios if r.id != radio.id]
            self.project.links = [l for l in self.project.links if radio.id not in (l.a_radio_id, l.b_radio_id)]
            self.changed()

    def delete_link(self):
        link = self.selected(self.links_table, self.project.links)
        if link:
            self.project.links.remove(link)
            self.changed()

    def select_dem(self):
        path = filedialog.askopenfilename(filetypes=[("Elevation GeoTIFF", "*.tif *.tiff")], parent=self)
        if path:
            self.project.terrain_path = str(Path(path).resolve())
            self.usgs.set(False)
            self.changed()
            self.status.set(f"Local terrain selected: {Path(path).name}. Enable USGS terrain to use automatic tiles instead.")

    def path_settings(self):
        def save(values):
            candidate = copy.deepcopy(self.project)
            candidate.earth_k = float(values['earth_k'])
            candidate.sample_spacing_m = float(values['sample_spacing_m'])
            candidate.terrain_path = values['terrain_path'].strip()
            self.apply(candidate)
        EditDialog(self, "Path calculation settings", [("earth_k", "Effective Earth radius factor", None), ("sample_spacing_m", "Terrain sample spacing (m)", None), ("terrain_path", "Local DEM path (blank = none)", None)], asdict(self.project), save)

    def analyze(self):
        if self.future:
            return
        if not self.project.links:
            self.status.set("Connect at least two radios before analyzing.")
            return
        snapshot = copy.deepcopy(self.project)
        selected_model, use_usgs = self.model.get(), self.usgs.get()
        revision = self.revision
        from .engine import analyze_network
        from .terrain import RasterTerrain
        def work():
            terrain = RasterTerrain(None if use_usgs else snapshot.terrain_path, spacing_m=snapshot.sample_spacing_m) if snapshot.terrain_path or use_usgs else None
            return revision, analyze_network(snapshot, terrain, selected_model)
        self.future = Future()
        future = self.future
        def run():
            try:
                future.set_result(work())
            except Exception as exc:
                future.set_exception(exc)
        # Closing the editor should not wait for remote tile download timeouts.
        threading.Thread(target=run, daemon=True).start()
        source = 'automatic USGS tiles' if use_usgs else f'local DEM: {snapshot.terrain_path}' if snapshot.terrain_path else 'provisional free space (no terrain)'
        self.status.set(f"Analyzing network using {source}. Downloads may take time; the editor remains available.")

    def poll(self):
        if self.future and self.future.done():
            try:
                revision, results = self.future.result()
                if revision == self.revision:
                    self.results = {result['link_id']: result for result in results}
                    self.status.set(f"Analyzed {len(results)} links. Select a link to inspect its signal budget and terrain profile.")
                    self.refresh()
                else:
                    self.status.set("Project changed during analysis. Recalculate to get current results.")
            except Exception as exc:
                self.status.set(f"Analysis failed: {exc}")
            self.future = None
        self.after(150, self.poll)

    def refresh(self):
        self.title(f"Jockstrap — {self.project.name}" + (" *" if self.dirty else ""))
        for tree in (self.sites_table, self.radios_table, self.links_table):
            tree.delete(*tree.get_children())
        sites = {s.id: s for s in self.project.sites}
        radios = {r.id: r for r in self.project.radios}
        for site in self.project.sites:
            self.sites_table.insert('', 'end', iid=site.id, text=site.name, values=(f"{site.lat:.5f}, {site.lon:.5f}",))
        for radio in self.project.radios:
            self.radios_table.insert('', 'end', iid=radio.id, text=radio.name, values=(sites[radio.site_id].name, radio.role, radio.equipment))
        for link in self.project.links:
            result = self.results.get(link.id, {})
            signals = [f"{result[key]['rx_dbm']:.1f}" if key in result else '—' for key in ('forward', 'reverse')]
            self.links_table.insert('', 'end', iid=link.id, text=link.name, values=(result.get('status', 'Not analyzed'), *signals))
        self.details.configure(state="normal")
        self.details.delete('1.0', 'end')
        self.details.configure(state="disabled")
        if not self.map:
            return
        self.map.delete_all_marker()
        self.map.delete_all_path()
        for site in self.project.sites:
            self.map.set_marker(site.lat, site.lon, text=site.name)
        for radio in self.project.radios:
            if radio.aim == 'fixed':
                site = sites[radio.site_id]
                positions = []
                for angle in (radio.azimuth_deg - radio.az_beamwidth_deg/2, radio.azimuth_deg, radio.azimuth_deg + radio.az_beamwidth_deg/2):
                    lon, lat, _ = GEOD.fwd(site.lon, site.lat, angle, 1000)
                    self.map.set_path([(site.lat, site.lon), (lat, lon)], color='#a78bfa', width=2)
                    positions.append((lat, lon))
                self.map.set_path(positions, color='#a78bfa', width=2)
        for link in self.project.links:
            a, b = sites[radios[link.a_radio_id].site_id], sites[radios[link.b_radio_id].site_id]
            status = self.results.get(link.id, {}).get('status', '')
            color = '#16a34a' if status == 'Meets planning checks' else '#dc2626' if status in ('Terrain obstructed', 'Insufficient margin', 'Incompatible settings') else '#d97706' if status == 'Fresnel clearance limited' else '#64748b'
            self.map.set_path([(a.lat, a.lon), (b.lat, b.lon)], color=color, width=3)

    def show_summary(self, *_):
        link = self.selected(self.links_table, self.project.links)
        result = self.results.get(link.id, {}) if link else {}
        self.details.configure(state="normal")
        self.details.delete('1.0', 'end')
        if result:
            self.details.insert('end', self.summary(result))
        self.details.configure(state="disabled")

    @staticmethod
    def summary(result):
        if 'error' in result:
            return result['status'] + '\n' + result['error']
        text = f"{result['name']} — {result['status']}\n{result['distance_km']:.2f} km | {result['model']}\n"
        for key in ('forward', 'reverse'):
            direction = result[key]
            text += f"{direction['tx_radio']} → {direction['rx_radio']}: {direction['rx_dbm']:.1f} dBm; margin after reserve {direction['margin_db']:+.1f} dB\n"
        text += f"A aim: {result['bearing_a_deg']:.1f}° / tilt {result['elevation_a_deg']:.2f}°; B aim: {result['bearing_b_deg']:.1f}° / tilt {result['elevation_b_deg']:.2f}°\n"
        if result['min_fresnel_clearance_m'] is not None:
            text += f"Minimum 60% Fresnel clearance: {result['min_fresnel_clearance_m']:.1f} m\n"
        return text + '\n' + '\n'.join(result['warnings'])

    def inspect_link(self):
        link = self.selected(self.links_table, self.project.links)
        result = self.results.get(link.id) if link else None
        if not result:
            self.status.set("Analyze the network first to inspect a link.")
            return
        window = tk.Toplevel(self)
        window.title(link.name)
        window.geometry("1000x750")
        text = tk.Text(window, height=12, wrap="word")
        text.pack(fill="x")
        text.insert('end', self.summary(result))
        text.configure(state='disabled')
        if result.get('profile'):
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            profile = result['profile']
            figure = Figure(figsize=(10, 4), tight_layout=True)
            axis = figure.add_subplot(111)
            distances = [x/1000 for x in profile['distance_m']]
            axis.plot(distances, profile['curved_terrain_m'], color='#92400e', label='Terrain + effective Earth curvature')
            axis.plot(distances, profile['sightline_m'], color='#2563eb', label='Antenna sightline')
            lower = [line - .6*radius for line, radius in zip(profile['sightline_m'], profile['fresnel_radius_m'])]
            upper = [line + .6*radius for line, radius in zip(profile['sightline_m'], profile['fresnel_radius_m'])]
            axis.fill_between(distances, lower, upper, color='#93c5fd', alpha=.35, label='60% first Fresnel zone')
            axis.set_xlabel('Distance (km)')
            axis.set_ylabel('Elevation (m, curvature-adjusted)')
            axis.legend()
            axis.grid(alpha=.2)
            canvas = FigureCanvasTkAgg(figure, master=window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

    def export(self):
        if not self.results:
            self.status.set("Analyze the network before exporting.")
            return
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('Analysis JSON', '*.json')], parent=self)
        if path:
            Path(path).write_text(json.dumps(dict(project=self.project.name, results=list(self.results.values())), indent=2, allow_nan=False)+'\n', encoding='utf-8')

    def confirm_discard(self):
        return not self.dirty or messagebox.askyesno("Unsaved project", "Discard unsaved changes?", parent=self)

    def new(self):
        if self.confirm_discard():
            self.project, self.path = Project(), None
            self.revision += 1
            self.results.clear()
            self.dirty = False
            self.refresh()

    def open(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(filetypes=[('Jockstrap project', '*.json')], parent=self)
        if path:
            try:
                project = Project.load(path)
                if project.terrain_path and not Path(project.terrain_path).is_absolute():
                    project.terrain_path = str((Path(path).resolve().parent / project.terrain_path).resolve())
                self.project, self.path = project, Path(path)
                self.revision += 1
                self.results.clear()
                self.dirty = False
                self.refresh()
                if self.map and self.project.sites:
                    self.map.set_position(self.project.sites[0].lat, self.project.sites[0].lon)
            except (ValueError, TypeError, OSError, KeyError) as exc:
                messagebox.showerror('Cannot open project', str(exc), parent=self)

    def save(self, save_as=False):
        path = self.path
        if save_as or path is None:
            selected = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('Jockstrap project', '*.json')], parent=self)
            if not selected:
                return
            path = Path(selected)
        try:
            self.project.save(path)
            self.path, self.dirty = path, False
            self.status.set(f"Saved {path.name}")
            self.refresh()
        except (ValueError, OSError) as exc:
            messagebox.showerror('Cannot save project', str(exc), parent=self)

    def close(self):
        if self.confirm_discard():
            self.destroy()
