plugins {
 id("com.android.application")
 id("org.jetbrains.kotlin.android")
 id("org.jetbrains.kotlin.plugin.compose")
}
android {
 namespace = "br.com.ktv.mobile"
 compileSdk = 35
 defaultConfig { applicationId = "br.com.ktv.mobile"; minSdk = 23; targetSdk = 35; versionCode = 5; versionName = "0.4.2" }
 buildFeatures { compose = true }
 compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
 kotlinOptions { jvmTarget = "17" }
}
dependencies {
 implementation(platform("androidx.compose:compose-bom:2024.09.00"))
 implementation("androidx.activity:activity-compose:1.9.2")
 implementation("androidx.fragment:fragment-ktx:1.8.5")
 implementation("androidx.compose.ui:ui")
 implementation("androidx.compose.ui:ui-tooling-preview")
 implementation("androidx.compose.material3:material3")
 implementation("androidx.compose.material:material-icons-extended")
 implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
 implementation("androidx.media3:media3-exoplayer:1.9.0")
 implementation("androidx.media3:media3-exoplayer-hls:1.9.0")
 implementation("androidx.media3:media3-exoplayer-rtsp:1.9.0")
 implementation("androidx.media3:media3-ui:1.9.0")
 implementation("androidx.media3:media3-cast:1.9.0")
 implementation("io.coil-kt:coil-compose:2.7.0")
 debugImplementation("androidx.compose.ui:ui-tooling")
}
