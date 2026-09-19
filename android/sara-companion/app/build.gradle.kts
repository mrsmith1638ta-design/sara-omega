plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.saraomega.companion"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.saraomega.companion"
        minSdk = 31
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "SARA_BASE_URL", "\"https://sara-omega-production.up.railway.app/\"")
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }

    buildTypes {
        debug {
            isDebuggable = true
        }
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            val ks = System.getenv("SARA_ANDROID_KEYSTORE_FILE")
            val kp = System.getenv("SARA_ANDROID_KEYSTORE_PASSWORD")
            val ka = System.getenv("SARA_ANDROID_KEY_ALIAS")
            val kpass = System.getenv("SARA_ANDROID_KEY_PASSWORD")
            if (!ks.isNullOrBlank() && !kp.isNullOrBlank() && !ka.isNullOrBlank() && !kpass.isNullOrBlank()) {
                signingConfig = signingConfigs.create("externalRelease") {
                    storeFile = file(ks)
                    storePassword = kp
                    keyAlias = ka
                    keyPassword = kpass
                }
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
}
