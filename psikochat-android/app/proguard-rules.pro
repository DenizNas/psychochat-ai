# Retrofit rules
-keepattributes Signature, InnerClasses, EnclosingMethod, AnnotationDefault, *Annotation*
-dontwarn retrofit2.**
-keep class retrofit2.** { *; }
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations

# Gson rules
-keepattributes Signature
-keepattributes *Annotation*
-dontwarn sun.misc.Unsafe
-keep class com.google.gson.** { *; }

# Keep Psychochat API Data Models fully intact (especially fields for Gson mapping)
-keep class com.psikochat.app.data.model.** { *; }
-keepclassmembers class com.psikochat.app.data.model.** { <fields>; }

# Keep SerializedName annotated fields
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

# OkHttp rules
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }

# WorkManager rules
-dontwarn androidx.work.**
-keep class androidx.work.** { *; }
