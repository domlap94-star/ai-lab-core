import java.io.FileInputStream
import java.net.URI
import java.util.Base64
import java.util.Properties

plugins {
    id("com.android.application")
    id("dev.flutter.flutter-gradle-plugin")
}

val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")

if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

fun decodedDartDefines(): Map<String, String> {
    val encoded = providers.gradleProperty("dart-defines").orNull.orEmpty()
    if (encoded.isBlank()) return emptyMap()
    return encoded.split(',').mapNotNull { item ->
        runCatching {
            String(Base64.getDecoder().decode(item), Charsets.UTF_8)
        }.getOrNull()?.takeIf { it.contains('=') }?.let { decoded ->
            decoded.substringBefore('=') to decoded.substringAfter('=')
        }
    }.toMap()
}

fun isSafeReleaseApiUrl(value: String?): Boolean {
    if (value.isNullOrBlank()) return false
    return runCatching {
        val uri = URI(value.trim().trimEnd('/'))
        val host = uri.host?.lowercase().orEmpty()
        uri.scheme.equals("https", ignoreCase = true) &&
            host.isNotBlank() &&
            uri.userInfo == null &&
            uri.query == null &&
            uri.fragment == null &&
            host !in setOf("10.0.2.2", "127.0.0.1", "localhost", "::1")
    }.getOrDefault(false)
}

val acceptanceBuildRequested = gradle.startParameter.taskNames.any { taskName ->
    taskName.contains("release", ignoreCase = true) ||
        taskName.contains("profile", ignoreCase = true)
}
if (acceptanceBuildRequested) {
    val apiBaseUrl = decodedDartDefines()["API_BASE_URL"]
    if (!isSafeReleaseApiUrl(apiBaseUrl)) {
        throw GradleException(
            "ANDROID_RELEASE_API_CONFIGURATION_INVALID: release/profile builds require " +
                "an explicit HTTPS API_BASE_URL that is not localhost, 127.0.0.1, or 10.0.2.2."
        )
    }
}

android {
    namespace = "com.example.frontend"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "pl.ailab.app"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            keyAlias = keystoreProperties["keyAlias"] as String
            keyPassword = keystoreProperties["keyPassword"] as String
            storeFile = keystoreProperties["storeFile"]?.let { file(it) }
            storePassword = keystoreProperties["storePassword"] as String
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
