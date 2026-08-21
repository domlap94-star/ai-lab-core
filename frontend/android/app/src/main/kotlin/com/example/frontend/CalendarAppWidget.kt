package com.example.frontend

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.RemoteViews
import org.json.JSONObject
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.TextStyle
import java.time.format.DateTimeFormatter
import java.util.Locale

class CalendarAppWidget : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        ids.forEach { update(context, manager, it) }
    }

    companion object {
        const val PREFERENCES = "calendar_widget_snapshot"
        const val SNAPSHOT = "safe_snapshot_json"
        private val dayIds = intArrayOf(
            R.id.day1, R.id.day2, R.id.day3, R.id.day4, R.id.day5, R.id.day6, R.id.day7,
            R.id.day8, R.id.day9, R.id.day10, R.id.day11, R.id.day12, R.id.day13, R.id.day14,
            R.id.day15, R.id.day16, R.id.day17, R.id.day18, R.id.day19, R.id.day20, R.id.day21,
            R.id.day22, R.id.day23, R.id.day24, R.id.day25, R.id.day26, R.id.day27, R.id.day28,
            R.id.day29, R.id.day30, R.id.day31, R.id.day32, R.id.day33, R.id.day34, R.id.day35,
            R.id.day36, R.id.day37, R.id.day38, R.id.day39, R.id.day40, R.id.day41, R.id.day42,
        )
        private val agendaIds = intArrayOf(R.id.agenda1, R.id.agenda2, R.id.agenda3, R.id.agenda4)

        fun updateAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, CalendarAppWidget::class.java)
            manager.getAppWidgetIds(component).forEach { update(context, manager, it) }
        }

        private fun update(context: Context, manager: AppWidgetManager, widgetId: Int) {
            val views = RemoteViews(context.packageName, R.layout.calendar_app_widget)
            val raw = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getString(SNAPSHOT, null)
            val snapshot = runCatching { raw?.let(::JSONObject) }.getOrNull()
            val yearMonth = runCatching {
                if (snapshot?.optInt("schema_version") == 1) YearMonth.of(snapshot.optInt("year"), snapshot.optInt("month")) else YearMonth.now()
            }.getOrDefault(YearMonth.now())
            views.setTextViewText(R.id.monthTitle, "${yearMonth.month.getDisplayName(TextStyle.FULL, Locale("pl"))} ${yearMonth.year}")
            val marked = mutableMapOf<LocalDate, Int>()
            val items = snapshot?.optJSONArray("items")
            if (items != null) for (i in 0 until items.length()) runCatching {
                val item = items.getJSONObject(i)
                var day = LocalDate.parse(item.getString("date"))
                val end = LocalDate.parse(item.optString("end_date", item.getString("date")))
                var guard = 0
                while (!day.isAfter(end) && guard < 42) {
                    marked[day] = (marked[day] ?: 0) + 1
                    day = day.plusDays(1)
                    guard++
                }
            }
            val first = yearMonth.atDay(1)
            var cursor = first.minusDays((first.dayOfWeek.value - 1).toLong())
            dayIds.forEachIndexed { index, viewId ->
                val count = marked[cursor] ?: 0
                val number = if (cursor == LocalDate.now()) "[${cursor.dayOfMonth}]" else "${cursor.dayOfMonth}"
                val indicator = when { count > 2 -> "•••"; count > 0 -> "•"; else -> "" }
                val label = if (indicator.isEmpty()) number else "$number\n$indicator"
                views.setTextViewText(viewId, label)
                views.setOnClickPendingIntent(viewId, pending(context, "/tasks?date=$cursor", 1000 + index))
                cursor = cursor.plusDays(1)
            }
            agendaIds.forEach { views.setTextViewText(it, "") }
            if (items == null || items.length() == 0) views.setTextViewText(R.id.agenda1, "Brak zaplanowanych pozycji")
            else for (i in 0 until minOf(items.length(), agendaIds.size)) {
                val item = items.getJSONObject(i)
                views.setTextViewText(agendaIds[i], "${dateRange(item)}  ${item.optString("title")}")
                views.setOnClickPendingIntent(agendaIds[i], pending(context, if (item.optString("kind") == "absence") "/tasks?absence_id=${item.optInt("id")}" else "/tasks/${item.optInt("id")}", 100 + i))
            }
            views.setTextViewText(R.id.lastUpdated, if (snapshot == null) "Brak zapisanych danych" else "Ostatnia aktualizacja: ${snapshot.optString("updated_at").take(16).replace('T', ' ')}")
            views.setOnClickPendingIntent(R.id.monthTitle, pending(context, "/tasks", 1))
            views.setOnClickPendingIntent(R.id.addTask, pending(context, "/tasks?create=1", 2))
            views.setOnClickPendingIntent(R.id.addAbsence, pending(context, "/tasks?absence=1", 3))
            manager.updateAppWidget(widgetId, views)
        }

        private fun pending(context: Context, path: String, code: Int): PendingIntent {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://next-stabil.local$path"), context, MainActivity::class.java)
            return PendingIntent.getActivity(context, code, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        }

        private fun dateRange(item: JSONObject): String {
            val start = LocalDate.parse(item.getString("date"))
            val end = LocalDate.parse(item.optString("end_date", item.getString("date")))
            val short = DateTimeFormatter.ofPattern("dd.MM", Locale("pl"))
            if (start == end) return start.format(short)
            if (start.year != end.year) {
                val full = DateTimeFormatter.ofPattern("dd.MM.yyyy", Locale("pl"))
                return "${start.format(full)}–${end.format(full)}"
            }
            if (start.month == end.month) return "${start.dayOfMonth.toString().padStart(2, '0')}–${end.format(short)}"
            return "${start.format(short)}–${end.format(short)}"
        }
    }
}
