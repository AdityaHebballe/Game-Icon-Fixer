#!/usr/bin/env python3

import os
import re
import gi
import glob
import html

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

APP_DIR = os.path.expanduser("~/.local/share/applications")
SYSTEM_STEAM_IDS = {"480", "1070560", "1391110"}

class SteamAppItemActionRow(Adw.ActionRow):
    def __init__(self, filename, filepath, name, game_id, current_wmclass, expected_wmclass, status, app_icon, fix_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        self.filepath = filepath
        self.name_val = name
        self.game_id = game_id
        self.current_wmclass = current_wmclass
        self.expected_wmclass = expected_wmclass
        self.status = status
        self.app_icon = app_icon
        self.fix_callback = fix_callback
        
        # Escape characters like & for Pango markup which ActionRow uses by default
        escaped_title = html.escape(self.name_val or self.filename)
        self.set_title(escaped_title)
        
        status_text = ""
        if self.status == "missing":
            status_text = f"Missing StartupWMClass. Will add: {self.expected_wmclass}"
        elif self.status == "incorrect":
            status_text = f"Incorrect WMClass ({self.current_wmclass}). Will change to: {self.expected_wmclass}"
        elif self.status == "correct":
            status_text = f"Already correct ({self.expected_wmclass})"
            
        self.set_subtitle(status_text)

        # Add game icon prefix
        game_icon = Gtk.Image(pixel_size=32)
        if self.app_icon and self.app_icon.startswith("/"):
            game_icon.set_from_file(self.app_icon)
        elif self.app_icon:
            game_icon.set_from_icon_name(self.app_icon)
        else:
            game_icon.set_from_icon_name("application-x-executable")
        self.add_prefix(game_icon)

        # Add per-status suffix (button for fixing or checkmark for correct)
        if status in ["missing", "incorrect"]:
             self.fix_btn = Gtk.Button(label="Fix", valign=Gtk.Align.CENTER)
             self.fix_btn.add_css_class("destructive-action")
             self.fix_btn.connect("clicked", self.on_fix_clicked)
             self.add_suffix(self.fix_btn)
        else:
             status_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
             status_icon.add_css_class("success")
             self.add_suffix(status_icon)
             
    def on_fix_clicked(self, button):
        if self.fix_callback:
            self.fix_callback(self)


class FaugusAppItemEntryRow(Adw.EntryRow):
    def __init__(self, filename, filepath, name, current_wmclass, app_icon, apply_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        self.filepath = filepath
        self.name_val = name
        self.current_wmclass = current_wmclass
        self.app_icon = app_icon
        self.apply_callback = apply_callback
        
        escaped_title = html.escape(self.name_val or self.filename)
        self.set_title(escaped_title)
        
        if self.current_wmclass:
            self.set_text(self.current_wmclass)
            
        # Add game icon prefix
        game_icon = Gtk.Image(pixel_size=32)
        if self.app_icon and self.app_icon.startswith("/"):
            game_icon.set_from_file(self.app_icon)
        elif self.app_icon:
            game_icon.set_from_icon_name(self.app_icon)
        else:
            game_icon.set_from_icon_name("application-x-executable")
        self.add_prefix(game_icon)
        
        # Apply button beside the entry
        self.apply_btn = Gtk.Button(label="Apply", valign=Gtk.Align.CENTER)
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.connect("clicked", self.on_apply_clicked)
        self.add_suffix(self.apply_btn)

    def on_apply_clicked(self, button):
        if self.apply_callback:
            # We fetch exactly what the user typed in the EntryRow
            new_wmclass = self.get_text().strip()
            self.apply_callback(self, new_wmclass)


class SteamIconFixerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Game Icon Fixer")
        self.set_default_size(700, 600)

        # Main box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # Header Bar
        self.header = Adw.HeaderBar()
        self.main_box.append(self.header)

        # ViewSwitcher Title at the center
        self.switcher_title = Adw.ViewSwitcherTitle()
        self.switcher_title.set_title("Game Icon Fixer")
        self.header.set_title_widget(self.switcher_title)

        # Refresh Button
        self.refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        self.refresh_btn.set_tooltip_text("Refresh List")
        self.refresh_btn.connect("clicked", self.on_refresh_clicked)
        self.header.pack_start(self.refresh_btn)

        # Status toast overlay wraps everything else
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_vexpand(True)
        self.main_box.append(self.toast_overlay)

        # ViewStack for Tabs
        self.view_stack = Adw.ViewStack()
        self.switcher_title.set_stack(self.view_stack)
        self.toast_overlay.set_child(self.view_stack)

        # ------------------- STEAM TAB -------------------
        self.steam_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        self.steam_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.steam_stack.set_vexpand(True)
        self.steam_container.append(self.steam_stack)
        
        steam_scrolled = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.steam_stack.add_named(steam_scrolled, "content")
        
        self.steam_pref_page = Adw.PreferencesPage()
        steam_scrolled.set_child(self.steam_pref_page)
        
        self.steam_needs_fix_group = Adw.PreferencesGroup(title="Games Needing Fixes")
        self.steam_pref_page.add(self.steam_needs_fix_group)
        
        self.steam_correct_group = Adw.PreferencesGroup(title="Properly Configured")
        self.steam_pref_page.add(self.steam_correct_group)
        
        self.steam_empty_state = Adw.StatusPage(
            title="No Steam Games",
            description="Could not find any Steam games in ~/.local/share/applications.",
            icon_name="emblem-default-symbolic"
        )
        self.steam_stack.add_named(self.steam_empty_state, "empty")
        
        self.steam_bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.steam_bottom_bar.set_halign(Gtk.Align.CENTER)
        self.steam_bottom_bar.set_margin_top(12)
        self.steam_bottom_bar.set_margin_bottom(12)
        
        self.steam_apply_btn = Gtk.Button(label="Apply Fix to All Games", css_classes=["suggested-action", "pill"])
        self.steam_apply_btn.connect("clicked", self.on_steam_apply_clicked)
        self.steam_bottom_bar.append(self.steam_apply_btn)
        self.steam_container.append(self.steam_bottom_bar)
        
        # We add Steam Tab using the standard Steam icon or a fallback
        self.view_stack.add_titled_with_icon(self.steam_container, "steam", "Steam", "steam")
        # If the 'steam' icon name doesn't exist, GTK prints a warning but falls back, many icon sets have 'steam'

        # ------------------ FAUGUS TAB -------------------
        self.faugus_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        self.faugus_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.faugus_stack.set_vexpand(True)
        self.faugus_container.append(self.faugus_stack)
        
        faugus_scrolled = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.faugus_stack.add_named(faugus_scrolled, "content")
        
        self.faugus_pref_page = Adw.PreferencesPage()
        
        # Instruction Banner
        instruction_str = "Press Alt + F2 and enter \"lg\" to open looking glass in GNOME. Navigate to the Windows tab, note the WMClass for your game while it's running, and enter it here."
        self.faugus_pref_page.set_description(instruction_str)
        
        faugus_scrolled.set_child(self.faugus_pref_page)
        
        self.faugus_group = Adw.PreferencesGroup(title="Faugus Launcher Games")
        self.faugus_pref_page.add(self.faugus_group)
        
        self.faugus_empty_state = Adw.StatusPage(
            title="No Faugus Games",
            description="Could not find any Faugus Launcher games in ~/.local/share/applications.",
            icon_name="emblem-default-symbolic"
        )
        self.faugus_stack.add_named(self.faugus_empty_state, "empty")
        
        self.view_stack.add_titled_with_icon(self.faugus_container, "faugus", "Faugus Launcher", "faugus-launcher")

        
        self.steam_items = []
        self.faugus_items = []
        self.load_desktop_files()

    def on_refresh_clicked(self, button):
        self.load_desktop_files()
        
    def show_toast(self, message):
        toast = Adw.Toast.new(message)
        self.toast_overlay.add_toast(toast)

    def load_desktop_files(self):
        # Clear existing Steam
        for item in self.steam_items:
            if item.status in ["missing", "incorrect"]:
                self.steam_needs_fix_group.remove(item)
            else:
                self.steam_correct_group.remove(item)
        self.steam_items.clear()
        
        # Clear existing Faugus
        for item in self.faugus_items:
            self.faugus_group.remove(item)
        self.faugus_items.clear()

        if not os.path.exists(APP_DIR):
            self.show_toast(f"Directory {APP_DIR} not found.")
            self.steam_stack.set_visible_child_name("empty")
            self.faugus_stack.set_visible_child_name("empty")
            self.steam_bottom_bar.set_visible(False)
            return

        desktop_files = glob.glob(os.path.join(APP_DIR, "*.desktop"))
            
        for d_file in desktop_files:
            app_data = self.parse_desktop_file(d_file)
            if not app_data:
                continue
                
            launcher = app_data["launcher"]
            
            if launcher == "steam":
                game_id = app_data["game_id"]
                if game_id in SYSTEM_STEAM_IDS:
                    continue
                    
                expected = f"steam_app_{game_id}"
                current = app_data.get("startup_wmclass")
                
                if current == expected:
                    status = "correct"
                else:
                    status = "missing" if current is None else "incorrect"
                
                row = SteamAppItemActionRow(
                    filename=os.path.basename(d_file),
                    filepath=d_file,
                    name=app_data.get("name"),
                    game_id=game_id,
                    current_wmclass=current,
                    expected_wmclass=expected,
                    status=status,
                    app_icon=app_data.get("icon"),
                    fix_callback=self.on_steam_fix_single_item
                )
                self.steam_items.append(row)
                if status == "correct":
                    self.steam_correct_group.add(row)
                else:
                    self.steam_needs_fix_group.add(row)
                    
            elif launcher == "faugus":
                current_wmclass = app_data.get("startup_wmclass")
                row = FaugusAppItemEntryRow(
                    title="WMClass", # We use entry row, the title displays within the entry placeholder or label
                    filename=os.path.basename(d_file),
                    filepath=d_file,
                    name=app_data.get("name"),
                    current_wmclass=current_wmclass,
                    app_icon=app_data.get("icon"),
                    apply_callback=self.on_faugus_apply_single_item
                )
                self.faugus_items.append(row)
                self.faugus_group.add(row)


        # Setup UI state for Steam
        steam_needing_fix = [item for item in self.steam_items if item.status in ("missing", "incorrect")]
        steam_correct = [item for item in self.steam_items if item.status == "correct"]

        self.steam_bottom_bar.set_visible(len(steam_needing_fix) > 0)
        self.steam_needs_fix_group.set_visible(len(steam_needing_fix) > 0)
        self.steam_correct_group.set_visible(len(steam_correct) > 0)

        if len(self.steam_items) == 0:
            self.steam_stack.set_visible_child_name("empty")
        else:
            self.steam_stack.set_visible_child_name("content")
            
        # Setup UI state for Faugus
        if len(self.faugus_items) == 0:
            self.faugus_stack.set_visible_child_name("empty")
        else:
            self.faugus_stack.set_visible_child_name("content")

    def parse_desktop_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            return None

        # Return dict: {launcher: "steam"|"faugus", ...}
        game_id = None
        launcher = None
        current_wmclass = None
        name = None
        icon = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("Name="):
                name = line.split("=", 1)[1]
            elif line.startswith("StartupWMClass="):
                current_wmclass = line.split("=", 1)[1]
            elif line.startswith("Icon="):
                icon = line.split("=", 1)[1]
            elif line.startswith("Exec="):
                # Check for steam
                match = re.search(r'steam://rungameid/(\d+)', line)
                if match:
                    game_id = match.group(1)
                    launcher = "steam"
                elif "faugus-run" in line:
                    launcher = "faugus"
                    
        if not launcher:
            return None
            
        return {
            "launcher": launcher,
            "game_id": game_id,
            "startup_wmclass": current_wmclass,
            "name": name,
            "icon": icon
        }

    # ------------- STEAM LOGIC -------------
    def on_steam_fix_single_item(self, item):
        success = self.apply_manual_fix_to_file(item.filepath, item.expected_wmclass)
        if success:
            self.show_toast(f"Fixed icon for {item.name_val or item.filename}")
            self.load_desktop_files()
        else:
            self.show_toast(f"Failed to fix {item.name_val or item.filename}")

    def on_steam_apply_clicked(self, button):
        fixed_count = 0
        items_to_fix = [item for item in self.steam_items if item.status in ("missing", "incorrect")]
        for item in items_to_fix:
            success = self.apply_manual_fix_to_file(item.filepath, item.expected_wmclass)
            if success:
                fixed_count += 1
                
        self.show_toast(f"Successfully fixed {fixed_count} game(s).")
        self.load_desktop_files()

    # ------------- FAUGUS LOGIC -------------
    def on_faugus_apply_single_item(self, row, new_wmclass):
        success = self.apply_manual_fix_to_file(row.filepath, new_wmclass)
        if success:
            if new_wmclass:
                self.show_toast(f"Updated WMClass for {row.name_val or row.filename} to '{new_wmclass}'")
            else:
                self.show_toast(f"Removed WMClass from {row.name_val or row.filename}")
            self.load_desktop_files()
        else:
            self.show_toast(f"Failed to update {row.name_val or row.filename}")

    # ------------- SHARED FILE I/O -------------
    def apply_manual_fix_to_file(self, filepath, new_wmclass):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            new_lines = []
            replaced = False
            for line in lines:
                if line.startswith("StartupWMClass="):
                    if new_wmclass:
                        new_lines.append(f"StartupWMClass={new_wmclass}\n")
                    replaced = True
                else:
                    new_lines.append(line)
                    
            if not replaced and new_wmclass:
                # Add it right after [Desktop Entry]
                final_lines = []
                for line in new_lines:
                    final_lines.append(line)
                    if line.strip() == "[Desktop Entry]":
                        final_lines.append(f"StartupWMClass={new_wmclass}\n")
                new_lines = final_lines
                
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return True
        except Exception as e:
            print(f"Error updating {filepath}: {e}")
            return False

class SteamIconFixerApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        Gtk.Window.set_default_icon_name("com.github.adityahebballe.GameIconFixer")
        self.win = SteamIconFixerWindow(application=app)
        self.win.present()

if __name__ == '__main__':
    app = SteamIconFixerApp(application_id="com.github.adityahebballe.GameIconFixer")
    app.run(None)
