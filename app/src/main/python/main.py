import sys
import os
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
from android.view import Gravity, ViewGroup
from android.net import Uri
from android.content import Intent, SharedPreferences, ActivityNotFoundException
from android.app import Activity
from android.os import Environment
from android.content.res import Configuration
from android.app import UiModeManager
from android.content import Context
from android.util import TypedValue
from android.graphics import Color
from java.lang import Thread
from java.io import File
from androidx.cardview.widget import CardView
from android.provider import DocumentsContract
from java.io import BufferedInputStream, FileOutputStream

# Global state management
class AppState:
    selected_font_path1 = None
    selected_font_path2 = None
    progress_bar = None
    progress_percent_text = None
    status_text = None
    merge_button = None
    settings_button = None
    current_step = 0
    total_steps = 6
    app_context = None

# Constants
OUTPUT_DIR_NAME = 'MergedFonts'
EN_PREVIEW = "The quick brown fox jumps over the lazy dog. 1234567890"
AR_PREVIEW = "سمَات مجّانِية، إختر منْ بين أكثر من ١٠٠ سمة مجانية او انشئ سماتك الخاصة هُنا في هذا التطبيق النظيف الرائع، وأظهر الابداع.١٢٣٤٦٥٧٨٩٠"
PREFS_NAME = 'FontMergerPrefs'

def get_output_dir(context):
    """Returns the absolute path to the output directory."""
    try:
        output_dir = os.path.join(
            context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS).toString(),
            OUTPUT_DIR_NAME
        )
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        return output_dir
    except Exception as e:
        AppState.status_text.setText(f"Error getting output dir: {str(e)}")
        return None

def update_progress(step_text):
    """Updates the progress bar and status text on the main thread."""
    def update_ui():
        AppState.current_step += 1
        progress_val = int((AppState.current_step / AppState.total_steps) * 100)
        AppState.progress_bar.setProgress(progress_val)
        AppState.progress_percent_text.setText(f"{progress_val}% ({AppState.current_step}/{AppState.total_steps})")
        AppState.status_text.setText(step_text)
    Python.runOnMainThread(update_ui)

def get_theme_color(context):
    """Get colors based on current theme."""
    is_dark = (context.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
    if is_dark:
        return Color.WHITE, Color.BLACK, Color.rgb(30, 30, 30) # Text, Background, Card
    else:
        return Color.BLACK, Color.WHITE, Color.rgb(240, 240, 240) # Text, Background, Card

def set_locale(context, lang_code):
    """Sets the application's locale."""
    config = context.getResources().getConfiguration()
    if lang_code == 'ar':
        config.setLocale(java.util.Locale('ar'))
    elif lang_code == 'en':
        config.setLocale(java.util.Locale('en'))
    else: # system
        config.setLocale(context.getResources().getSystem().getConfiguration().getLocales().get(0))
    context.createConfigurationContext(config)

def apply_theme_and_locale(activity):
    """Applies theme and locale from SharedPreferences."""
    prefs = activity.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    theme_pref = prefs.getString('theme', 'system')
    lang_pref = prefs.getString('language', 'system')
    
    ui_manager = activity.getSystemService(Context.UI_MODE_SERVICE)
    if theme_pref == 'light':
        ui_manager.setNightMode(UiModeManager.MODE_NIGHT_NO)
    elif theme_pref == 'dark':
        ui_manager.setNightMode(UiModeManager.MODE_NIGHT_YES)
    else:
        ui_manager.setNightMode(UiModeManager.MODE_NIGHT_AUTO)
        
    set_locale(activity, lang_pref)
    
    if AppState.app_context:
        try:
            current_view = activity.findViewById(1) # a unique ID for the main layout
            setup_main_layout(activity)
        except:
            setup_settings_layout(activity)

# --- Font Processing Core ---
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
    finally:
        sys.argv = saved_argv
    if os.path.exists(out):
        temp_files.append(out)
        return out
    return path

def merge_fonts_thread(font_path1, font_path2):
    """
    Core function to merge fonts, create previews, and save the output.
    This runs in a separate thread.
    """
    AppState.current_step = 0
    try:
        processing_dir = tempfile.mkdtemp()
        temp_files = []
        
        update_progress("جاري تنظيف الخطوط...")
        arabic_ranges = "U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+0660-0669"
        latin_range = "U+0020-007F,U+00A0-00FF"
        
        subsetted_path1 = subset_font(font_path1, latin_range, temp_files)
        subsetted_path2 = subset_font(font_path2, arabic_ranges, temp_files)

        update_progress("جاري دمج الخطوط...")
        merger = Merger()
        merged_font_obj = merger.merge([subsetted_path1, subsetted_path2])
        
        output_dir = get_output_dir(AppState.app_context)
        if not output_dir:
            raise Exception("Failed to create output directory.")
            
        merged_font_path = os.path.join(output_dir, "merged_font.ttf")
        merged_font_obj.save(merged_font_path)
        
        update_progress("جاري إنشاء معاينة الخط...")
        preview_name = f"preview_light_{os.path.basename(merged_font_path).split('.')[0]}.jpg"
        preview_path = os.path.join(output_dir, preview_name)
        create_preview(merged_font_path, preview_path)
        
        update_progress("جاري إنشاء معاينة الخط (داكن)...")
        preview_dark_name = f"preview_dark_{os.path.basename(merged_font_path).split('.')[0]}.jpg"
        preview_dark_path = os.path.join(output_dir, preview_dark_name)
        create_preview(merged_font_path, preview_dark_path, bg_color=(18,18,18), text_color="white")
        
        update_progress("اكتمل الدمج. فتح المجلد...")
        def open_folder():
            uri = Uri.parse("content://com.android.externalstorage.documents/tree/primary%3ADownload%2FMergedFonts")
            intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(uri, DocumentsContract.Document.MIME_TYPE_DIR)
            try:
                AppState.app_context.startActivity(intent)
            except ActivityNotFoundException:
                Toast.makeText(AppState.app_context, "لا يوجد تطبيق لفتح هذا المجلد.", Toast.LENGTH_LONG).show()
        Python.runOnMainThread(open_folder)

        update_progress("اكتمل بنجاح!")
        def show_success_toast():
            Toast.makeText(
                AppState.app_context,
                "تم الدمج بنجاح. تم الحفظ في مجلد 'MergedFonts' في مساحة التخزين الداخلية.",
                Toast.LENGTH_LONG
            ).show()
            AppState.progress_bar.setVisibility(ProgressBar.INVISIBLE)
            AppState.progress_percent_text.setVisibility(TextView.INVISIBLE)
            AppState.status_text.setText("اضغط على زر الدمج لدمج الخطوط.")
        Python.runOnMainThread(show_success_toast)
        
    except Exception as e:
        traceback.print_exc()
        def show_error_toast():
            Toast.makeText(
                AppState.app_context,
                f"فشل الدمج: {str(e)}",
                Toast.LENGTH_LONG
            ).show()
            AppState.progress_bar.setVisibility(ProgressBar.INVISIBLE)
            AppState.progress_percent_text.setVisibility(TextView.INVISIBLE)
            AppState.status_text.setText(f"فشل الدمج: {str(e)}")
        Python.runOnMainThread(show_error_toast)
        
    finally:
        try:
            shutil.rmtree(processing_dir)
        except:
            pass

def create_preview(font_path, out_path, bg_color="white", text_color="black"):
    """Creates a high-quality font preview image."""
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)
    
    font_size = 100
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()
        
    reshaped_ar = ArabicReshaper().reshape(AR_PREVIEW)
    bidi_ar = get_display(reshaped_ar)
    draw.text((W/2, H/2 - 50), bidi_ar, font=font, fill=text_color, anchor="mm")
    
    draw.text((W/2, H/2 + 50), EN_PREVIEW, font=font, fill=text_color, anchor="mm")
    
    img.save(out_path, "JPEG", quality=95)

# --- UI Setup ---
def setup_main_layout(activity):
    AppState.app_context = activity.getApplicationContext()
    
    text_color, bg_color, card_color = get_theme_color(activity)

    layout = LinearLayout(activity)
    layout.setOrientation(LinearLayout.VERTICAL)
    layout.setGravity(Gravity.CENTER)
    layout.setLayoutParams(ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
    layout.setPadding(64, 64, 64, 64)
    layout.setBackgroundColor(bg_color)
    layout.setId(1)

    title_text = TextView(activity)
    title_text.setText("دمج الخطوط")
    title_text.setTextSize(TypedValue.COMPLEX_UNIT_SP, 28)
    title_text.setGravity(Gravity.CENTER)
    title_text.setTextColor(text_color)
    title_text.setPadding(0, 0, 0, 48)
    layout.addView(title_text)

    card_layout = CardView(activity)
    card_layout.setCardBackgroundColor(card_color)
    card_layout.setRadius(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 16, activity.getResources().getDisplayMetrics()))
    card_layout.setCardElevation(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 4, activity.getResources().getDisplayMetrics()))
    card_layout.setLayoutParams(LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT))

    font_select_card = LinearLayout(activity)
    font_select_card.setOrientation(LinearLayout.VERTICAL)
    font_select_card.setPadding(64, 64, 64, 64)
    
    select_font_button1 = Button(activity, None, android.R.attr.buttonStyleSmall)
    select_font_button1.setText("اختر الخط الأول")
    select_font_button1.setOnClickListener(lambda v: activity.startActivityForResult(Intent(Intent.ACTION_GET_CONTENT).setType("font/*"), 1))
    font_select_card.addView(select_font_button1)
    AppState.select_font_button1 = select_font_button1

    select_font_button2 = Button(activity, None, android.R.attr.buttonStyleSmall)
    select_font_button2.setText("اختر الخط الثاني")
    select_font_button2.setOnClickListener(lambda v: activity.startActivityForResult(Intent(Intent.ACTION_GET_CONTENT).setType("font/*"), 2))
    font_select_card.addView(select_font_button2)
    AppState.select_font_button2 = select_font_button2
    
    card_layout.addView(font_select_card)
    layout.addView(card_layout)

    status_text = TextView(activity)
    status_text.setText("الرجاء اختيار خطين للدمج.")
    status_text.setGravity(Gravity.CENTER)
    status_text.setPadding(0, 32, 0, 32)
    status_text.setTextColor(text_color)
    layout.addView(status_text)
    AppState.status_text = status_text
    
    progress_layout = LinearLayout(activity)
    progress_layout.setOrientation(LinearLayout.HORIZONTAL)
    progress_layout.setGravity(Gravity.CENTER)
    
    progress_bar = ProgressBar(activity, None, android.R.attr.progressBarStyleHorizontal)
    progress_bar.setMax(100)
    progress_bar.setIndeterminate(False)
    progress_bar.setLayoutParams(LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT, 1))
    progress_bar.setVisibility(ProgressBar.INVISIBLE)
    progress_layout.addView(progress_bar)
    AppState.progress_bar = progress_bar
    
    progress_percent_text = TextView(activity)
    progress_percent_text.setText("0%")
    progress_percent_text.setGravity(Gravity.CENTER)
    progress_percent_text.setTextColor(text_color)
    progress_percent_text.setPadding(16, 0, 0, 0)
    progress_percent_text.setVisibility(TextView.INVISIBLE)
    progress_layout.addView(progress_percent_text)
    
    layout.addView(progress_layout)
    AppState.progress_percent_text = progress_percent_text

    merge_button = Button(activity)
    merge_button.setText("دمج الخطوط")
    def on_merge_clicked(v):
        if AppState.selected_font_path1 and AppState.selected_font_path2:
            AppState.progress_bar.setVisibility(ProgressBar.VISIBLE)
            AppState.progress_percent_text.setVisibility(TextView.VISIBLE)
            AppState.current_step = 0
            Thread(lambda: merge_fonts_thread(AppState.selected_font_path1, AppState.selected_font_path2)).start()
        else:
            Toast.makeText(activity, "الرجاء اختيار خطين للدمج.", Toast.LENGTH_SHORT).show()
    merge_button.setOnClickListener(on_merge_clicked)
    layout.addView(merge_button)
    AppState.merge_button = merge_button
    
    settings_button = Button(activity)
    settings_button.setText("الإعدادات")
    settings_button.setOnClickListener(lambda v: setup_settings_layout(activity))
    layout.addView(settings_button)
    AppState.settings_button = settings_button

    activity.setContentView(layout)

def setup_settings_layout(activity):
    prefs = activity.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    text_color, bg_color, card_color = get_theme_color(activity)
    current_theme = prefs.getString('theme', 'system')
    current_language = prefs.getString('language', 'system')

    layout = LinearLayout(activity)
    layout.setOrientation(LinearLayout.VERTICAL)
    layout.setGravity(Gravity.CENTER_HORIZONTAL)
    layout.setPadding(64, 64, 64, 64)
    layout.setBackgroundColor(bg_color)
    layout.setId(2)

    title_text = TextView(activity)
    title_text.setText("الإعدادات")
    title_text.setTextSize(TypedValue.COMPLEX_UNIT_SP, 28)
    title_text.setTextColor(text_color)
    title_text.setGravity(Gravity.CENTER)
    title_text.setPadding(0, 0, 0, 48)
    layout.addView(title_text)
    
    card_layout = CardView(activity)
    card_layout.setCardBackgroundColor(card_color)
    card_layout.setRadius(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 16, activity.getResources().getDisplayMetrics()))
    card_layout.setCardElevation(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 4, activity.getResources().getDisplayMetrics()))
    card_layout.setLayoutParams(LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT))

    settings_content = LinearLayout(activity)
    settings_content.setOrientation(LinearLayout.VERTICAL)
    settings_content.setPadding(64, 64, 64, 64)
    
    theme_label = TextView(activity)
    theme_label.setText("الثيم")
    theme_label.setPadding(0, 0, 0, 8)
    theme_label.setTextColor(text_color)
    settings_content.addView(theme_label)

    theme_group = RadioGroup(activity)
    theme_group.setOrientation(LinearLayout.VERTICAL)
    settings_content.addView(theme_group)

    light_rb = RadioButton(activity)
    light_rb.setText("فاتح")
    light_rb.setTag('light')
    theme_group.addView(light_rb)

    dark_rb = RadioButton(activity)
    dark_rb.setText("داكن")
    dark_rb.setTag('dark')
    theme_group.addView(dark_rb)

    system_theme_rb = RadioButton(activity)
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
        apply_theme_and_locale(activity)

    theme_group.setOnCheckedChangeListener(on_theme_changed)

    lang_label = TextView(activity)
    lang_label.setText("اللغة")
    lang_label.setPadding(0, 32, 0, 8)
    lang_label.setTextColor(text_color)
    settings_content.addView(lang_label)

    lang_group = RadioGroup(activity)
    lang_group.setOrientation(LinearLayout.VERTICAL)
    settings_content.addView(lang_group)

    ar_rb = RadioButton(activity)
    ar_rb.setText("العربية")
    ar_rb.setTag('ar')
    lang_group.addView(ar_rb)

    en_rb = RadioButton(activity)
    en_rb.setText("الإنجليزية")
    en_rb.setTag('en')
    lang_group.addView(en_rb)

    system_lang_rb = RadioButton(activity)
    system_lang_rb.setText("النظام")
    system_lang_rb.setTag('system')
    lang_group.addView(system_lang_rb)
    
    if current_language == 'ar':
        ar_rb.setChecked(True)
    elif current_language == 'en':
        en_rb.setChecked(True)
    else:
        system_lang_rb.setChecked(True)

    def on_lang_changed(group, checkedId):
        tag = group.findViewById(checkedId).getTag()
        editor = prefs.edit()
        editor.putString('language', tag)
        editor.apply()
        apply_theme_and_locale(activity)

    lang_group.setOnCheckedChangeListener(on_lang_changed)
    
    card_layout.addView(settings_content)
    layout.addView(card_layout)

    back_button = Button(activity)
    back_button.setText("عودة")
    back_button.setOnClickListener(lambda v: setup_main_layout(activity))
    back_button.setPadding(0, 32, 0, 0)
    layout.addView(back_button)

    activity.setContentView(layout)

def main(activity):
    AppState.app_context = activity.getApplicationContext()
    apply_theme_and_locale(activity)
    setup_main_layout(activity)
    
    def on_activity_result(requestCode, resultCode, data):
        if resultCode == Activity.RESULT_OK and data and data.getData():
            uri = data.getData()
            try:
                temp_dir = activity.getCacheDir().getAbsolutePath()
                temp_file_name = f"font_{requestCode}.ttf"
                temp_file_path = os.path.join(temp_dir, temp_file_name)
                
                content_resolver = activity.getContentResolver()
                input_stream = content_resolver.openInputStream(uri)
                
                with open(temp_file_path, 'wb') as output_stream:
                    buf = bytearray(4096)
                    while True:
                        bytes_read = input_stream.read(buf)
                        if bytes_read == -1:
                            break
                        output_stream.write(buf[:bytes_read])
                
                if requestCode == 1:
                    AppState.selected_font_path1 = temp_file_path
                    AppState.select_font_button1.setText(f"الخط الأول: {os.path.basename(temp_file_path)}")
                elif requestCode == 2:
                    AppState.selected_font_path2 = temp_file_path
                    AppState.select_font_button2.setText(f"الخط الثاني: {os.path.basename(temp_file_path)}")
                
                Toast.makeText(activity, "تم اختيار الخط بنجاح.", Toast.LENGTH_SHORT).show()
            except Exception as e:
                traceback.print_exc()
                Toast.makeText(activity, f"خطأ في اختيار الخط: {e}", Toast.LENGTH_LONG).show()
                AppState.status_text.setText(f"خطأ في اختيار الخط: {str(e)}")

    activity.addOnActivityResultListener(on_activity_result)
