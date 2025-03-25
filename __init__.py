#https://youtube.com/playlist?list=PLNizloUxMUXLHNHn2-0Wmdf2YtygXcmop 
#Linked File Sync Panel.
#autorun=False
#|▮∎ ∥ ⫴① ② ③ ④ ⑤ ⑥ ⑦ ⑧ ⑨
#bpy.ops.view3d.modal_draw_operator('INVOKE_DEFAULT', text=textinfo_, duration=5)
bl_info = {
    "name": "Linked File Updater",
    "author": "fables alive games",
    "version": (1, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Linked Files Tab",
    "description": "Automatically checks and updates linked files when changes are detected",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

import bpy
import os
import time

linked_files = {}

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

def get_linked_files():
    """Finds all linked files in the scene and records their last modified times."""
    linked_files_data = {}
    
    for lib in bpy.data.libraries:
        if lib.filepath:
            filepath = bpy.path.abspath(lib.filepath)
            if os.path.exists(filepath):
                linked_files_data[filepath] = {
                    "library": lib,
                    "last_modified": os.path.getmtime(filepath)
                }
    
    return linked_files_data

def update_linked_files():
    """Updates linked files when changes are detected."""
    global linked_files
    
    current_linked_files = get_linked_files()
    updated_files = []
    
    for filepath, data in current_linked_files.items():
        if filepath in linked_files:
            if data["last_modified"] > linked_files[filepath]["last_modified"]:
                try:
                    data["library"].reload()
                    updated_files.append(os.path.basename(filepath))
                except Exception as e:
                    print(f"Error updating file: {filepath}, Error: {str(e)}")
        
    linked_files = current_linked_files
    
    return updated_files

def check_linked_files():
    """Timer function - checks linked files at specified intervals."""
    props = bpy.context.window_manager.linked_file_updater
    
    if not props.is_monitoring:
        return
    
    current_time = time.time()
    if current_time - props.last_check_time >= props.check_interval:
        props.last_check_time = current_time
        updated_files = update_linked_files()
        
        if updated_files:
            message = f"Updated files: {', '.join(updated_files)}"
            print(message)
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


class OBJECT_PT_toggle_LinkedFileSyncPanel(bpy.types.Operator):
    bl_idname = "wm.toggle_linked_file_sync_panel"
    bl_label = "Toggle Panel"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        context.window_manager.linked_file_sync_panel_visible = not context.window_manager.linked_file_sync_panel_visible

        if(context.window_manager.linked_file_sync_panel_visible):
            bpy.ops.view3d.toggle_n_panel_command_box()

        return {'FINISHED'}
    

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
        
        row = layout.row()
        row.enabled = True
        row.prop(props, "check_interval")
        
        if props.is_monitoring:
            layout.operator("linked_file.toggle_monitoring", text="Stop Monitoring", icon='PAUSE')
        else:
            layout.operator("linked_file.toggle_monitoring", text="Start Monitoring", icon='PLAY')
        
        layout.operator("linked_file.manual_update", text="Manual Update", icon='FILE_REFRESH')
        
        box = layout.box()
        box.label(text="Linked Files:")
        
        if not linked_files:
            box.label(text="No linked files found.")
        else:
            for filepath in linked_files:
                row = box.row()
                row.label(text=os.path.basename(filepath))

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

class LINKED_FILE_OT_manual_update(bpy.types.Operator):
    """Manually update linked files"""
    bl_idname = "linked_file.manual_update"
    bl_label = "Manual Update"
    
    def execute(self, context):
        props = context.window_manager.linked_file_updater
        was_monitoring = props.is_monitoring
        
        global linked_files
        linked_files = get_linked_files()
        
        for filepath, data in linked_files.items():
            try:
                data["library"].reload()
                self.report({'INFO'}, f"{os.path.basename(filepath)} updated.")
            except Exception as e:
                self.report({'ERROR'}, f"Error updating file: {os.path.basename(filepath)}, Error: {str(e)}")
        
        props.is_monitoring = was_monitoring
                
        return {'FINISHED'}

# Timer callback function
def timer_callback():
    check_linked_files()
    return bpy.context.window_manager.linked_file_updater.check_interval

classes = (
    OBJECT_PT_toggle_LinkedFileSyncPanel,
    LinkedFileProperties,
    VIEW3D_PT_linked_file_updater,
    LINKED_FILE_OT_toggle_monitoring,
    LINKED_FILE_OT_manual_update,
)

timer = None

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Add properties to WindowManager
    bpy.types.WindowManager.linked_file_updater = bpy.props.PointerProperty(type=LinkedFileProperties)
    bpy.types.WindowManager.linked_file_sync_panel_visible = bpy.props.BoolProperty(default=False)   
    global timer
    if timer is None:
        timer = bpy.app.timers.register(timer_callback, persistent=True)

def unregister():
    global timer
    if timer is not None and bpy.app.timers.is_registered(timer_callback):
        bpy.app.timers.unregister(timer_callback)
    timer = None
    
    del bpy.types.WindowManager.linked_file_sync_panel_visible

    if hasattr(bpy.types.WindowManager, "linked_file_updater"):
        del bpy.types.WindowManager.linked_file_updater
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
    bpy.ops.wm.toggle_linked_file_sync_panel()