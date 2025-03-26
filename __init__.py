import bpy
import os
import time
import subprocess
import platform

linked_files = {}
DEVNULL = open(os.devnull, 'wb')

class LinkedFileProperties(bpy.types.PropertyGroup):
    check_interval: bpy.props.FloatProperty(
        name="Check Interval (seconds)",
        description="Time interval for checking linked files",
        default=1.0,
        min=0.1,
        max=60.0
    )
    is_monitoring: bpy.props.BoolProperty(
        name="Monitoring Active",
        description="Status of linked file monitoring",
        default=False
    )
    last_check_time: bpy.props.FloatProperty(
        default=0.0
    )
    watch_mode: bpy.props.EnumProperty(
        name="Watch Mode",
        description="Method to use for file monitoring",
        items=[
            ('DIRECT', "Direct", "Monitor files directly (default)"),
            ('AGGRESSIVE', "Aggressive", "Force filesystem refresh (slower but more reliable)"),
        ],
        default='AGGRESSIVE'
    )

def force_filesystem_update(filepath):
    """Force the filesystem to update by calling external commands."""
    if not os.path.exists(filepath):
        return False
    
    try:
        # Different approaches based on OS
        system = platform.system().lower()
        
        if system == 'windows':
            # Windows: use dir command to refresh
            subprocess.call(['dir', '/b', filepath], shell=True, stdout=DEVNULL, stderr=DEVNULL)
        elif system in ['darwin', 'linux']:
            # macOS/Linux: use ls
            subprocess.call(['ls', '-la', filepath], stdout=DEVNULL, stderr=DEVNULL)
            
        # Force read a small portion of the file
        with open(filepath, 'rb') as f:
            f.seek(0)
            f.read(1024)  # Read first 1KB
            
        return True
    except:
        return False

def get_direct_file_info(filepath):
    """Get file info directly via stat."""
    try:
        stat = os.stat(filepath)
        return {
            "mtime": stat.st_mtime,
            "size": stat.st_size
        }
    except:
        return None

def get_linked_files():
    """Finds all linked files in the scene and records their last modified times."""
    linked_files_data = {}
    
    for lib in bpy.data.libraries:
        if lib.filepath:
            # Get absolute path
            filepath = bpy.path.abspath(lib.filepath)
            if os.path.exists(filepath):
                # Force filesystem to recognize changes
                force_filesystem_update(filepath)
                
                # Get file info
                file_info = get_direct_file_info(filepath)
                if file_info:
                    linked_files_data[filepath] = {
                        "library": lib,
                        "last_modified": file_info["mtime"],
                        "size": file_info["size"],
                        "lib_name": lib.name
                    }
    
    return linked_files_data

def update_linked_files():
    """Updates linked files when changes are detected."""
    global linked_files
    props = bpy.context.window_manager.linked_file_updater
    
    current_linked_files = get_linked_files()
    updated_files = []
    
    # Check for updates
    for filepath, data in current_linked_files.items():
        if filepath in linked_files:
            old_info = linked_files[filepath]
            
            # Check if file changed (time or size)
            if (data["last_modified"] > old_info["last_modified"] or 
                data["size"] != old_info["size"]):
                
                lib_name = data["lib_name"]
                print(f"Change detected in {lib_name}. Last modified: {time.ctime(data['last_modified'])}")
                print(f"  Old time: {time.ctime(old_info['last_modified'])}, New time: {time.ctime(data['last_modified'])}")
                print(f"  Old size: {old_info['size']}, New size: {data['size']}")
                
                try:
                    # Force reload the library
                    if props.watch_mode == 'AGGRESSIVE':
                        force_filesystem_update(filepath)
                    data["library"].reload()
                    updated_files.append(lib_name)
                except Exception as e:
                    print(f"Error updating {lib_name}: {str(e)}")
    
    # Update our cache
    linked_files = current_linked_files
    
    return updated_files

def poll_files():
    """Alternative polling method for aggressive mode."""
    props = bpy.context.window_manager.linked_file_updater
    updated = []
    
    if props.watch_mode == 'AGGRESSIVE':
        # Get fresh list with filesystem refresh
        global linked_files
        for filepath in linked_files:
            force_filesystem_update(filepath)
        
        fresh_files = get_linked_files()
        
        # Check for updates
        for filepath, data in fresh_files.items():
            if filepath in linked_files:
                old_info = linked_files[filepath]
                
                # Check for changes
                if (data["last_modified"] > old_info["last_modified"] or 
                    data["size"] != old_info["size"]):
                    
                    try:
                        print(f"Direct poll: change in {data['lib_name']}")
                        data["library"].reload()
                        updated.append(data["lib_name"])
                    except:
                        pass
        
        # Update our cache
        linked_files = fresh_files
    
    return updated

def check_linked_files():
    """Timer function - checks linked files at specified intervals."""
    props = bpy.context.window_manager.linked_file_updater
    
    # Stop if monitoring is off
    if not props.is_monitoring:
        return props.check_interval
    
    current_time = time.time()
    updated_files = []
    
    # Normal interval based check
    if current_time - props.last_check_time >= props.check_interval:
        props.last_check_time = current_time
        updated_files = update_linked_files()
    
    # Always do direct polling in aggressive mode
    elif props.watch_mode == 'AGGRESSIVE':
        poll_updated = poll_files()
        if poll_updated:
            updated_files.extend(poll_updated)
    
    # Handle updates
    if updated_files:
        message = f"Updated: {', '.join(updated_files)}"
        print(message)
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    
    # Always check rapidly in aggressive mode, otherwise use the interval
    return 0.2 if props.watch_mode == 'AGGRESSIVE' else props.check_interval

class VIEW3D_PT_linked_file_updater(bpy.types.Panel):
    """Linked File Sync Updater Panel"""
    bl_label = "Linked Sync File Updater"
    bl_idname = "VIEW3D_PT_linked_file_updater"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Command Box'
    
    @classmethod
    def poll(cls, context):
        return getattr(context.window_manager, "linked_file_sync_panel_visible", True)
    
    def draw_header_preset(self, context):
        layout = self.layout
        layout.operator("wm.toggle_linked_file_sync_panel", text="", icon='CANCEL', emboss=False)

    def draw(self, context):
        layout = self.layout
        props = context.window_manager.linked_file_updater
        
        # Monitoring controls
        box = layout.box()
        col = box.column()
        
        row = col.row()
        row.prop(props, "watch_mode", expand=True)
        
        row = col.row()
        row.prop(props, "check_interval")
        
        row = col.row()
        if props.is_monitoring:
            row.operator("linked_file.toggle_monitoring", text="Stop Monitoring", icon='PAUSE')
        else:
            row.operator("linked_file.toggle_monitoring", text="Start Monitoring", icon='PLAY')
        
        # Update controls
        row = layout.row(align=True)
        row.operator("linked_file.force_check", text="Check Now", icon='VIEWZOOM')
        row.operator("linked_file.manual_update", text="Update All", icon='FILE_REFRESH')
        
        # Linked files display
        box = layout.box()
        box.label(text="Linked Files:")
        
        if not linked_files:
            box.label(text="No linked files found.")
        else:
            for filepath, data in linked_files.items():
                row = box.row()
                lib_name = data.get("lib_name", os.path.basename(filepath))
                row.label(text=lib_name)

class LINKED_FILE_OT_toggle_monitoring(bpy.types.Operator):
    """Start or stop monitoring"""
    bl_idname = "linked_file.toggle_monitoring"
    bl_label = "Toggle Monitoring"
    
    def execute(self, context):
        props = context.window_manager.linked_file_updater
        props.is_monitoring = not props.is_monitoring
        
        if props.is_monitoring:
            global linked_files
            linked_files = get_linked_files()
            props.last_check_time = time.time()
            self.report({'INFO'}, "Linked file monitoring started.")
        else:
            self.report({'INFO'}, "Linked file monitoring stopped.")
            
        return {'FINISHED'}

class LINKED_FILE_OT_force_check(bpy.types.Operator):
    """Force an immediate check for file changes"""
    bl_idname = "linked_file.force_check"
    bl_label = "Check Now"
    
    def execute(self, context):
        global linked_files
        
        # Force filesystem refresh
        for filepath in linked_files:
            force_filesystem_update(filepath)
        
        # Get updated file info
        updated_files = update_linked_files()
        
        if updated_files:
            self.report({'INFO'}, f"Updated {len(updated_files)} files.")
        else:
            self.report({'INFO'}, "No changes detected.")
            
        return {'FINISHED'}

class LINKED_FILE_OT_manual_update(bpy.types.Operator):
    """Force reload all linked files"""
    bl_idname = "linked_file.manual_update"
    bl_label = "Update All"
    
    def execute(self, context):
        global linked_files
        
        # Get fresh list
        linked_files = get_linked_files()
        
        # Update all
        updated = 0
        for filepath, data in linked_files.items():
            try:
                data["library"].reload()
                updated += 1
            except Exception as e:
                print(f"Error updating {data.get('lib_name', os.path.basename(filepath))}: {str(e)}")
        
        self.report({'INFO'}, f"Reloaded {updated} linked files.")
        return {'FINISHED'}

classes = (
    LinkedFileProperties,
    VIEW3D_PT_linked_file_updater,
    LINKED_FILE_OT_toggle_monitoring,
    LINKED_FILE_OT_force_check,
    LINKED_FILE_OT_manual_update,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Add properties to WindowManager
    bpy.types.WindowManager.linked_file_updater = bpy.props.PointerProperty(type=LinkedFileProperties)
    
    # Register timer
    bpy.app.timers.register(check_linked_files, first_interval=0.1, persistent=True)

def unregister():
    if bpy.app.timers.is_registered(check_linked_files):
        bpy.app.timers.unregister(check_linked_files)
    
    global DEVNULL
    if DEVNULL:
        DEVNULL.close()
    
    if hasattr(bpy.types.WindowManager, "linked_file_updater"):
        del bpy.types.WindowManager.linked_file_updater
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()