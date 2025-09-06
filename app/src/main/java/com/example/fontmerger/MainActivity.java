package com.example.fontmerger;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.app.AppCompatDelegate;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.preference.PreferenceManager;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.util.Locale;

public class MainActivity extends AppCompatActivity {
    private static final int REQUEST_CODE_ARABIC = 1;
    private static final int REQUEST_CODE_ENGLISH = 2;
    private static final int STORAGE_PERMISSION_CODE = 3;
    private EditText arabicFontPath, englishFontPath;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        applyTheme();  // تطبيق الثيم من الإعدادات
        applyLanguage();  // تطبيق اللغة من الإعدادات
        applyCustomFont();  // تطبيق الخط المخصص
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        arabicFontPath = findViewById(R.id.arabic_font_path);
        englishFontPath = findViewById(R.id.english_font_path);
        Button mergeButton = findViewById(R.id.merge_button);

        arabicFontPath.setOnClickListener(v -> pickFile(REQUEST_CODE_ARABIC));
        englishFontPath.setOnClickListener(v -> pickFile(REQUEST_CODE_ENGLISH));

        mergeButton.setOnClickListener(v -> {
            if (checkPermissions()) {
                mergeFonts();
            } else {
                requestPermissions();
            }
        });

        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
    }

    private void pickFile(int requestCode) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");  // للخطوط TTF/OTF
        startActivityForResult(intent, requestCode);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode == Activity.RESULT_OK && data != null) {
            Uri uri = data.getData();
            String path = uri.getPath();  // يمكن تحسين للحصول على مسار حقيقي إذا لزم
            if (requestCode == REQUEST_CODE_ARABIC) {
                arabicFontPath.setText(path);
            } else if (requestCode == REQUEST_CODE_ENGLISH) {
                englishFontPath.setText(path);
            }
        }
    }

    private boolean checkPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            return Environment.isExternalStorageManager();
        } else {
            int read = ContextCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE);
            int write = ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE);
            return read == PackageManager.PERMISSION_GRANTED && write == PackageManager.PERMISSION_GRANTED;
        }
    }

    private void requestPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        } else {
            ActivityCompat.requestPermissions(this, new String[]{
                    Manifest.permission.READ_EXTERNAL_STORAGE,
                    Manifest.permission.WRITE_EXTERNAL_STORAGE
            }, STORAGE_PERMISSION_CODE);
        }
    }

    private void mergeFonts() {
        String aPath = arabicFontPath.getText().toString();
        String ePath = englishFontPath.getText().toString();
        if (aPath.isEmpty() || ePath.isEmpty()) {
            // عرض رسالة خطأ
            return;
        }

        Python py = Python.getInstance();
        PyObject pyf = py.getModule("merge_script");  // اسم السكربت البايثون
        pyf.callAttr("main_merge", aPath, ePath);  // استدعاء دالة دمج معدلة
        // عرض نتيجة أو log
    }

    private void applyTheme() {
        SharedPreferences prefs = PreferenceManager.getDefaultSharedPreferences(this);
        String theme = prefs.getString("theme_pref", "system");
        switch (theme) {
            case "light":
                AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO);
                break;
            case "dark":
                AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES);
                break;
            default:
                AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM);
        }
    }

    private void applyLanguage() {
        SharedPreferences prefs = PreferenceManager.getDefaultSharedPreferences(this);
        String lang = prefs.getString("language_pref", "system");
        Locale locale;
        switch (lang) {
            case "arabic":
                locale = new Locale("ar");
                break;
            case "english":
                locale = new Locale("en");
                break;
            default:
                locale = Locale.getDefault();
        }
        Locale.setDefault(locale);
        Configuration config = new Configuration();
        config.setLocale(locale);
        getBaseContext().getResources().updateConfiguration(config, getBaseContext().getResources().getDisplayMetrics());
    }

    private void applyCustomFont() {
        // افترض خط Amiri.ttf في assets/fonts
        // Typeface customFont = Typeface.createFromAsset(getAssets(), "fonts/Amiri.ttf");
        // ثم قم بتعيينه على جميع النصوص، أو استخدم في الثيم
        // مثال: ((TextView) findViewById(R.id.some_text)).setTypeface(customFont);
    }
                       }
