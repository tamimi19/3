import sys
import os
import platform
import shutil
import tempfile
import traceback
from fontTools.ttLib import TTFont
from fontTools.merge import Merger
from fontTools.subset import main as subset_main
from PIL import Image, ImageDraw, ImageFont, features
from arabic_reshaper import ArabicReshaper
from bidi.algorithm import get_display
from com.chaquo.python import Python
from android.widget import Button, TextView, LinearLayout, Toast, ProgressBar, RadioGroup, RadioButton, CheckBox
from android.view import Gravity, ViewGroup, View
from android.net import Uri
from android.content import Intent, SharedPreferences
from android.app import Activity
from android.os import Environment
from android.content.res import Configuration
from android.app.UiModeManager
from android.content import Context
from android.util import TypedValue
from android.graphics import Color
from java.lang import Thread

# Global state management
class AppState:
    selected_font_path1 = None
    selected_font_path2 = None
    progress_bar = None
    progress_percent_text = None
    status_text = None
    merge_button = None
    console = Console()
    
# Constants
FONT_DIR = "/sdcard/fonts"
OUTPUT_DIR_NAME = 'MergedFonts'
EN_PREVIEW = "The quick brown fox jumps over the lazy dog. 1234567890"
AR_PREVIEW = "سمَات مجّانِية، إختر منْ بين أكثر من ١٠٠ سمة مجانية او انشئ سماتك الخاصة هُنا في هذا التطبيق النظيف الرائع، وأظهر الابداع.١٢٣٤٥٦٧٨٩٠"

def get_output_dir():
    """Returns the absolute path to the output directory."""
    try:
        context = Python.getContext()
        output_dir = os.path.join(
            context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS).toString(),
            OUTPUT_DIR_NAME
        )
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        return output_dir
    except Exception as e:
        AppState.console.log(f"[ERROR] Failed to get output directory: {e}")
        return None

def apply_theme(activity, theme_pref):
    """Applies the selected theme (light, dark, or system)."""
    ui_manager = activity.getSystemService(Context.UI_MODE_SERVICE)
    if theme_pref == 'light':
        ui_manager.setNightMode(UiModeManager.MODE_NIGHT_NO)
    elif theme_pref == 'dark':
        ui_manager.setNightMode(UiModeManager.MODE_NIGHT_YES)
    else:
        ui_manager.setNightMode(UiModeManager.MODE_NIGHT_AUTO)

def get_string_res(context, res_name):
    """Gets string resource by name."""
    res_id = context.getResources().getIdentifier(res_name, 'string', context.getPackageName())
    if res_id != 0:
        return context.getString(res_id)
    return res_name.replace('_', ' ').capitalize() # Fallback

def get_theme_color(context, is_light_theme):
    if is_light_theme:
        return Color.BLACK, Color.WHITE
    else:
        return Color.WHITE, Color.BLACK

# --- Font Processing Core ---
def try_unify_units(paths):
    """Unifies unitsPerEm for a list of fonts."""
    fonts = [TTFont(p) for p in paths]
    units = [f['head'].unitsPerEm for f in fonts]
    target = max(units)
    for f in fonts:
        if f['head'].unitsPerEm != target:
            f['head'].unitsPerEm = target
            # Note: This is a simplification. Proper scaling of glyphs is complex
            # and requires more advanced font-editing tools not available here.
    return fonts

def subset_font(path, unicodes, temp_files):
    """Subsets a font to keep only specified unicodes."""
    base, _ = os.path.splitext(path)
    out = os.path.join(tempfile.gettempdir(), os.path.basename(base) + "_sub.ttf")
    saved_argv = sys.argv[:]
    try:
        sys.argv = ["pyftsubset", path, f"--unicodes={unicodes}", f"--output-file={out}", "--no-hinting"]
        subset_main()
    except SystemExit:
        pass
    except Exception as ex:
        AppState.console.log(f"[WARN] Subset failed for {os.path.basename(path)}: {ex}")
        out = path
    finally:
        sys.argv = saved_argv
    if os.path.exists(out):
        temp_files.append(out)
        AppState.console.log(f"pyftsubset: Subset font")
        return out
    return path

def merge_fonts_and_create_preview(font_path1, font_path2, preview_dark=False):
    """
    Core function to merge fonts, create previews, and save the output.
    This runs in a separate thread.
    """
    try:
        processing_dir = tempfile.mkdtemp()
        temp_files = []
        
        # 1. Unify units
        fonts_to_merge = try_unify_units([font_path1, font_path2])
        
        # 2. Subset fonts
        arabic_ranges = "U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+0660-0669"
        ascii_range = "U+0020-007F"
        
        subsetted_path1 = subset_font(font_path1, ascii_range, temp_files)
        subsetted_path2 = subset_font(font_path2, arabic_ranges, temp_files)

        # 3. Merge fonts
        merger = Merger()
        merged_font_obj = merger.merge([subsetted_path1, subsetted_path2])
        
        output_dir = get_output_dir()
        if not output_dir:
            raise Exception("Failed to create output directory.")
            
        merged_font_path = os.path.join(output_dir, "merged_font.ttf")
        merged_font_obj.save(merged_font_path)

        # 4. Create previews
        preview_name = f"preview_{os.path.basename(merged_font_path).split('.')[0]}.jpg"
        preview_path = os.path.join(output_dir, preview_name)
        
        create_preview(merged_font_path, preview_path)
        
        if preview_dark:
            preview_dark_name = f"preview_{os.path.basename(merged_font_path).split('.')[0]}_dark.jpg"
            preview_dark_path = os.path.join(output_dir, preview_dark_name)
            create_preview(merged_font_path, preview_dark_path, bg_color=(18,18,18), text_color="white")
            
        # Success message
        Python.runOnMainThread(lambda: Toast.makeText(
            Python.getContext(),
            f"تم الدمج بنجاح. تم الحفظ في: {output_dir}",
            Toast.LENGTH_LONG
        ).show())
        
    except Exception as e:
        Python.runOnMainThread(lambda: Toast.makeText(
            Python.getContext(),
            f"فشل الدمج: {str(e)}",
            Toast.LENGTH_LONG
        ).show())
        AppState.console.log(traceback.format_exc())
    finally:
        try:
            shutil.rmtree(processing_dir)
        except:
            pass
        Python.runOnMainThread(lambda: AppState.progress_bar.setVisibility(ProgressBar.INVISIBLE))
        Python.runOnMainThread(lambda: AppState.progress_percent_text.setVisibility(TextView.INVISIBLE))
        Python.runOnMainThread(lambda: AppState.status_text.setText("اضغط على زر الدمج لدمج الخطوط."))

def create_preview(font_path, out_path, bg_color="white", text_color="black"):
    """Creates a high-quality font preview image."""
    try:
        W, H = 1920, 1080
        img = Image.new("RGB", (W, H), bg_color)
        draw = ImageDraw.Draw(img)
        
        font_size = 100
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()
            
        # Draw Arabic preview
        reshaped_ar = ArabicReshaper().reshape(AR_PREVIEW)
        bidi_ar = get_display(reshaped_ar)
        draw.text((W/2, H/2 - 50), bidi_ar, font=font, fill=text_color, anchor="mm")
        
        # Draw English preview
        draw.text((W/2, H/2 + 50), EN_PREVIEW, font=font, fill=text_color, anchor="mm")
        
        img.save(out_path, "JPEG", quality=95)
        
    except Exception as e:
        AppState.console.log(f"Preview creation failed: {e}")

# --- Main App UI and Logic ---
def setup_main_layout(activity):
    """Sets up the main UI layout and listeners."""
    context = Python.getContext()
    
    prefs = context.getSharedPreferences('settings', Context.MODE_PRIVATE)
    is_light_theme = (context.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_NO
    text_color, bg_color = get_theme_color(context, is_light_theme)

    # Main layout
    layout = LinearLayout(activity)
    layout.setOrientation(LinearLayout.VERTICAL)
    layout.setGravity(Gravity.CENTER)
    layout.setLayoutParams(ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
    layout.setPadding(32, 32, 32, 32)
    layout.setBackgroundColor(bg_color)
    
    # Title TextView
    title_text = TextView(context)
    title_text.setText("دمج الخطوط")
    title_text.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24)
    title_text.setGravity(Gravity.CENTER)
    title_text.setTextColor(text_color)
    layout.addView(title_text)
    
    # Font 1 selection button
    select_font_button1 = Button(context)
    select_font_button1.setText("اختر الخط الأول")
    select_font_button1.setOnClickListener(lambda v: activity.startActivityForResult(Intent(Intent.ACTION_GET_CONTENT).setType("font/*"), 1))
    layout.addView(select_font_button1)
    AppState.select_font_button1 = select_font_button1

    # Font 2 selection button
    select_font_button2 = Button(context)
    select_font_button2.setText("اختر الخط الثاني")
    select_font_button2.setOnClickListener(lambda v: activity.startActivityForResult(Intent(Intent.ACTION_GET_CONTENT).setType("font/*"), 2))
    layout.addView(select_font_button2)
    AppState.select_font_button2 = select_font_button2

    # Status TextView
    status_text = TextView(context)
    status_text.setText("الرجاء اختيار خطين للدمج.")
    status_text.setGravity(Gravity.CENTER)
    status_text.setPadding(0, 16, 0, 16)
    status_text.setTextColor(text_color)
    layout.addView(status_text)
    AppState.status_text = status_text
    
    # Progress bar and percentage
    progress_layout = LinearLayout(activity)
    progress_layout.setOrientation(LinearLayout.VERTICAL)
    progress_layout.setGravity(Gravity.CENTER)
    progress_layout.setLayoutParams(LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))

    progress_bar = ProgressBar(context, None, android.R.attr.progressBarStyleHorizontal)
    progress_bar.setMax(100)
    progress_bar.setVisibility(ProgressBar.INVISIBLE)
    progress_layout.addView(progress_bar)
    AppState.progress_bar = progress_bar

    progress_percent_text = TextView(context)
    progress_percent_text.setText("0%")
    progress_percent_text.setGravity(Gravity.CENTER)
    progress_percent_text.setTextColor(text_color)
    progress_percent_text.setVisibility(TextView.INVISIBLE)
    progress_layout.addView(progress_percent_text)
    AppState.progress_percent_text = progress_percent_text
    
    layout.addView(progress_layout)

    # Merge button
    merge_button = Button(context)
    merge_button.setText("دمج الخطوط")
    def on_merge_clicked(v):
        if AppState.selected_font_path1 and AppState.selected_font_path2:
            AppState.status_text.setText("جاري دمج الخطوط...")
            AppState.progress_bar.setVisibility(ProgressBar.VISIBLE)
            AppState.progress_percent_text.setVisibility(TextView.VISIBLE)
            # Start the merge process in a new thread
            Thread(lambda: merge_fonts_and_create_preview(AppState.selected_font_path1, AppState.selected_font_path2)).start()
        else:
            Toast.makeText(context, "الرجاء اختيار خطين للدمج.", Toast.LENGTH_SHORT).show()
    merge_button.setOnClickListener(on_merge_clicked)
    layout.addView(merge_button)
    AppState.merge_button = merge_button
    
    # Settings button
    settings_button = Button(context)
    settings_button.setText("الإعدادات")
    settings_button.setOnClickListener(lambda v: setup_settings_layout(activity))
    layout.addView(settings_button)

    activity.setContentView(layout)

def setup_settings_layout(activity):
    """Sets up the settings UI layout and listeners."""
    context = Python.getContext()
    
    prefs = context.getSharedPreferences('settings', Context.MODE_PRIVATE)
    is_light_theme = (context.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_NO
    text_color, bg_color = get_theme_color(context, is_light_theme)
    current_theme = prefs.getString('theme', 'system')
    current_language = prefs.getString('language', 'system')

    # Main layout
    layout = LinearLayout(activity)
    layout.setOrientation(LinearLayout.VERTICAL)
    layout.setGravity(Gravity.CENTER)
    layout.setLayoutParams(ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
    layout.setPadding(32, 32, 32, 32)
    layout.setBackgroundColor(bg_color)

    # Title
    title_text = TextView(context)
    title_text.setText("الإعدادات")
    title_text.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24)
    title_text.setGravity(Gravity.CENTER)
    title_text.setTextColor(text_color)
    layout.addView(title_text)

    # Theme section
    theme_label = TextView(context)
    theme_label.setText("الثيم")
    theme_label.setPadding(0, 32, 0, 8)
    theme_label.setTextColor(text_color)
    layout.addView(theme_label)

    theme_group = RadioGroup(context)
    theme_group.setOrientation(LinearLayout.VERTICAL)
    layout.addView(theme_group)

    light_rb = RadioButton(context)
    light_rb.setText("فاتح")
    light_rb.setTag('light')
    theme_group.addView(light_rb)

    dark_rb = RadioButton(context)
    dark_rb.setText("داكن")
    dark_rb.setTag('dark')
    theme_group.addView(dark_rb)

    system_theme_rb = RadioButton(context)
    system_theme_rb.setText("النظام")
    system_theme_rb.setTag('system')
    theme_group.addView(system_theme_rb)
    
    if current_theme == 'light':
        light_rb.setChecked(True)
    elif current_theme == 'dark':
        dark_rb.setChecked(True)
    else:
        system_theme_rb.setChecked(True)

    def on_theme_changed(group, checkedId):
        tag = group.findViewById(checkedId).getTag()
        editor = prefs.edit()
        editor.putString('theme', tag)
        editor.apply()
        apply_theme(activity, tag)

    theme_group.setOnCheckedChangeListener(on_theme_changed)

    # Back button
    back_button = Button(context)
    back_button.setText("عودة")
    back_button.setOnClickListener(lambda v: setup_main_layout(activity))
    layout.addView(back_button)

    activity.setContentView(layout)

def main(activity):
    """Entry point for the Android app."""
    context = Python.getContext()
    
    # Set the initial view
    setup_main_layout(activity)
    
    # Handle the result from the file picker
    def on_activity_result(requestCode, resultCode, data):
        if resultCode == Activity.RESULT_OK and data:
            uri = data.getData()
            try:
                # Android requires content resolver to get the actual file path from Uri
                # We will use a temporary copy
                content_resolver = context.getContentResolver()
                temp_file = os.path.join(tempfile.gettempdir(), os.path.basename(uri.getPath()))
                with content_resolver.openInputStream(uri) as input_stream:
                    with open(temp_file, 'wb') as output_stream:
                        shutil.copyfileobj(input_stream, output_stream)
                
                if requestCode == 1:
                    AppState.selected_font_path1 = temp_file
                    AppState.select_font_button1.setText(f"الخط الأول: {os.path.basename(temp_file)}")
                elif requestCode == 2:
                    AppState.selected_font_path2 = temp_file
                    AppState.select_font_button2.setText(f"الخط الثاني: {os.path.basename(temp_file)}")
                
                Toast.makeText(context, "تم اختيار الخط بنجاح.", Toast.LENGTH_SHORT).show()
            except Exception as e:
                Toast.makeText(context, f"خطأ في اختيار الخط: {e}", Toast.LENGTH_LONG).show()

    activity.addOnActivityResultListener(on_activity_result)
