package com.example.frontend

import android.content.Context
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "pl.ailab.app/calendar_widget")
            .setMethodCallHandler { call, result ->
                if (call.method != "saveSnapshot") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                val snapshot = call.arguments as? String
                val parsed = runCatching { snapshot?.let(::JSONObject) }.getOrNull()
                val forbidden = snapshot?.contains(Regex("access_token|refresh_token|client_name|description|note", RegexOption.IGNORE_CASE)) == true
                if (snapshot == null || snapshot.length > 32_000 || forbidden || parsed?.optInt("schema_version") != 1 || (parsed.optJSONArray("items")?.length() ?: 0) > 40) {
                    result.error("invalid_snapshot", "Widget snapshot rejected", null)
                    return@setMethodCallHandler
                }
                getSharedPreferences(CalendarAppWidget.PREFERENCES, Context.MODE_PRIVATE)
                    .edit().putString(CalendarAppWidget.SNAPSHOT, snapshot).apply()
                CalendarAppWidget.updateAll(this)
                result.success(null)
            }
    }
}
