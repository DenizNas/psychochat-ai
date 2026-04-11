import os

BASE_DIR = r"c:\Users\deniz\OneDrive\Masaüstü\YAZILIM\psikochat-ai\psikochat-android"

files = {}

# 1. Gradle Files
files["settings.gradle.kts"] = """
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "Psikochat"
include(":app")
"""

files["build.gradle.kts"] = """
plugins {
    id("com.android.application") version "8.2.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.0" apply false
}
"""

files["gradle.properties"] = """
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
"""

files["app/build.gradle.kts"] = """
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.psikochat.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.psikochat.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildFeatures {
        compose = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.1"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    
    implementation(platform("androidx.compose:compose-bom:2024.02.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.navigation:navigation-compose:2.7.7")

    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.11.0")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("androidx.datastore:datastore-preferences:1.0.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
}
"""

# 2. Manifest & Resources
files["app/src/main/AndroidManifest.xml"] = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.psikochat.app">
    <uses-permission android:name="android.permission.INTERNET" />
    <application
        android:allowBackup="true"
        android:label="Psikochat"
        android:supportsRtl="true"
        android:theme="@style/Theme.Psikochat"
        android:networkSecurityConfig="@xml/network_security_config">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/Theme.Psikochat">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""

files["app/src/main/res/xml/network_security_config.xml"] = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">10.0.2.2</domain>
        <domain includeSubdomains="true">localhost</domain>
    </domain-config>
</network-security-config>
"""

files["app/src/main/res/values/themes.xml"] = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.Psikochat" parent="android:Theme.Material.Light.NoActionBar" />
</resources>
"""

# 3. Source Files - Base
pkg = "app/src/main/java/com/psikochat/app"

files[f"{pkg}/MainActivity.kt"] = """package com.psikochat.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.psikochat.app.ui.auth.LoginScreen
import com.psikochat.app.ui.chat.ChatScreen
import com.psikochat.app.ui.theme.PsikochatTheme
import com.psikochat.app.data.local.TokenManager

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val tokenManager = TokenManager(this)
        setContent {
            PsikochatTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val navController = rememberNavController()
                    NavHost(navController = navController, startDestination = "login") {
                        composable("login") { LoginScreen(navController, tokenManager) }
                        composable("chat") { ChatScreen(navController, tokenManager) }
                    }
                }
            }
        }
    }
}
"""

files[f"{pkg}/ui/theme/Color.kt"] = """package com.psikochat.app.ui.theme
import androidx.compose.ui.graphics.Color
val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val Pink80 = Color(0xFFEFB8C8)
val DarkBackground = Color(0xFF0f172a)
val DarkSurface = Color(0xFF1e293b)
val AccentPrimary = Color(0xFF6366f1)
val DangerRed = Color(0xFFef4444)
val SystemChatBubble = Color(0xFF334155)
"""

files[f"{pkg}/ui/theme/Theme.kt"] = """package com.psikochat.app.ui.theme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
private val DarkColorScheme = darkColorScheme(
    primary = AccentPrimary,
    secondary = PurpleGrey80,
    tertiary = Pink80,
    background = DarkBackground,
    surface = DarkSurface
)
@Composable
fun PsikochatTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
"""

files[f"{pkg}/data/local/TokenManager.kt"] = """package com.psikochat.app.data.local
import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class TokenManager(private val context: Context) {
    companion object { val TOKEN_KEY = stringPreferencesKey("jwt_token") }
    fun getToken(): Flow<String?> = context.dataStore.data.map { it[TOKEN_KEY] }
    suspend fun saveToken(token: String) { context.dataStore.edit { it[TOKEN_KEY] = token } }
    suspend fun clearToken() { context.dataStore.edit { it.remove(TOKEN_KEY) } }
}
"""

files[f"{pkg}/data/model/Models.kt"] = """package com.psikochat.app.data.model
import com.google.gson.annotations.SerializedName

data class AuthRequest(val username: String, val password: String)
data class AuthResponse(val access_token: String, val token_type: String, val username: String)
data class RegisterResponse(val message: String)
data class ChatRequest(val text: String, val language: String = "tr")
data class ChatResponse(val emotion: String, val risk: String, val response: String, val emergency_contact: String?)
data class HistoryItem(val role: String, val text: String)

sealed class Resource<T>(val data: T? = null, val message: String? = null) {
    class Success<T>(data: T) : Resource<T>(data)
    class Error<T>(message: String, data: T? = null) : Resource<T>(data, message)
    class Loading<T> : Resource<T>()
}
"""

files[f"{pkg}/data/api/AuthInterceptor.kt"] = """package com.psikochat.app.data.api
import com.psikochat.app.data.local.TokenManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(private val tokenManager: TokenManager) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = runBlocking { tokenManager.getToken().first() }
        val request = chain.request().newBuilder()
        if (!token.isNullOrEmpty()) {
            request.addHeader("Authorization", "Bearer $token")
        }
        return chain.proceed(request.build())
    }
}
"""

files[f"{pkg}/data/api/PsikoApi.kt"] = """package com.psikochat.app.data.api
import com.psikochat.app.data.model.*
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface PsikoApi {
    @POST("/login")
    suspend fun login(@Body request: AuthRequest): AuthResponse
    
    @POST("/register")
    suspend fun register(@Body request: AuthRequest): RegisterResponse

    @POST("/predict")
    suspend fun sendMessage(@Body request: ChatRequest): ChatResponse

    @GET("/history")
    suspend fun getHistory(): List<HistoryItem>
}
"""

files[f"{pkg}/data/api/RetrofitClient.kt"] = """package com.psikochat.app.data.api
import com.psikochat.app.data.local.TokenManager
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {
    private const val BASE_URL = "http://10.0.2.2:8000" // For Android Emulator
    
    fun create(tokenManager: TokenManager): PsikoApi {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BODY }
        val authInterceptor = AuthInterceptor(tokenManager)
        
        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
            
        return Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(PsikoApi::class.java)
    }
}
"""

files[f"{pkg}/data/repository/AuthRepository.kt"] = """package com.psikochat.app.data.repository
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.AuthRequest
import com.psikochat.app.data.model.Resource

class AuthRepository(private val api: PsikoApi) {
    suspend fun login(user: String, pass: String): Resource<String> {
        return try {
            val res = api.login(AuthRequest(user, pass))
            Resource.Success(res.access_token)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Bilinmeyen bir hata oluştu")
        }
    }
    suspend fun register(user: String, pass: String): Resource<Boolean> {
        return try {
            api.register(AuthRequest(user, pass))
            Resource.Success(true)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Kayıt başarısız")
        }
    }
}
"""

files[f"{pkg}/data/repository/ChatRepository.kt"] = """package com.psikochat.app.data.repository
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.ChatRequest
import com.psikochat.app.data.model.ChatResponse
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.model.Resource

class ChatRepository(private val api: PsikoApi) {
    suspend fun getHistory(): Resource<List<HistoryItem>> {
        return try {
            val res = api.getHistory()
            Resource.Success(res)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Geçmiş yüklenemedi")
        }
    }
    
    suspend fun sendMessage(text: String): Resource<ChatResponse> {
        return try {
            val res = api.sendMessage(ChatRequest(text))
            Resource.Success(res)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Mesaj gönderilemedi")
        }
    }
}
"""

files[f"{pkg}/ui/auth/AuthViewModel.kt"] = """package com.psikochat.app.ui.auth
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class AuthViewModel(private val repository: AuthRepository, private val tokenManager: TokenManager) : ViewModel() {
    private val _authState = MutableStateFlow<Resource<Boolean>>(Resource.Success(false))
    val authState: StateFlow<Resource<Boolean>> = _authState
    
    fun login(user: String, pass: String) {
        viewModelScope.launch {
            _authState.value = Resource.Loading()
            when (val res = repository.login(user, pass)) {
                is Resource.Success -> {
                    res.data?.let { tokenManager.saveToken(it) }
                    _authState.value = Resource.Success(true)
                }
                is Resource.Error -> _authState.value = Resource.Error(res.message ?: "Hata")
                else -> {}
            }
        }
    }
    
    fun register(user: String, pass: String) {
        viewModelScope.launch {
            _authState.value = Resource.Loading()
            when (val res = repository.register(user, pass)) {
                is Resource.Success -> login(user, pass) // Oto login
                is Resource.Error -> _authState.value = Resource.Error(res.message ?: "Hata")
                else -> {}
            }
        }
    }
}
"""

files[f"{pkg}/ui/auth/LoginScreen.kt"] = """package com.psikochat.app.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.repository.AuthRepository
import com.psikochat.app.data.model.Resource
import kotlinx.coroutines.launch
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

@Composable
fun LoginScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repo = AuthRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return AuthViewModel(repo, tokenManager) as T
        }
    }
    val viewModel: AuthViewModel = viewModel(factory = factory)
    
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    val authState by viewModel.authState.collectAsState()
    
    val scope = rememberCoroutineScope()
    
    // Check if directly logged in
    LaunchedEffect(Unit) {
        tokenManager.getToken().collect { token ->
            if (!token.isNullOrEmpty()) {
                navController.navigate("chat") { popUpTo("login") { inclusive = true } }
            }
        }
    }
    
    if (authState is Resource.Success && (authState.data == true)) {
        LaunchedEffect(Unit) {
            navController.navigate("chat") { popUpTo("login") { inclusive = true } }
        }
    }
    
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("Psikochat-AI", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.primary)
        Spacer(modifier = Modifier.height(32.dp))
        
        OutlinedTextField(
            value = username, onValueChange = { username = it },
            label = { Text("Kullanıcı Adı") },
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedTextField(
            value = password, onValueChange = { password = it },
            label = { Text("Şifre") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(modifier = Modifier.height(16.dp))
        
        if (authState is Resource.Loading) {
            CircularProgressIndicator()
        } else {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Button(onClick = { viewModel.login(username, password) }, modifier = Modifier.weight(1f)) {
                    Text("Giriş Yap")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(onClick = { viewModel.register(username, password) }, modifier = Modifier.weight(1f)) {
                    Text("Kayıt Ol")
                }
            }
        }
        
        if (authState is Resource.Error) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(text = authState.message ?: "Hata", color = MaterialTheme.colorScheme.error)
        }
    }
}
"""

files[f"{pkg}/ui/chat/ChatViewModel.kt"] = """package com.psikochat.app.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.ChatRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class ChatViewModel(private val repository: ChatRepository) : ViewModel() {
    private val _messages = MutableStateFlow<List<HistoryItem>>(emptyList())
    val messages: StateFlow<List<HistoryItem>> = _messages
    
    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error
    
    private val _crisisAlert = MutableStateFlow<String?>(null)
    val crisisAlert: StateFlow<String?> = _crisisAlert
    
    fun loadHistory() {
        viewModelScope.launch {
            _isLoading.value = true
            when(val res = repository.getHistory()) {
                is Resource.Success -> {
                    _messages.value = res.data ?: emptyList()
                    if(_messages.value.isEmpty()) {
                        _messages.value = listOf(HistoryItem("assistant", "Merhaba! Ben sana destek olmak için tasarlanmış empatik bir yapay zekayım. Bugün nasıl hissediyorsun?"))
                    }
                }
                is Resource.Error -> _error.value = res.message
                else -> {}
            }
            _isLoading.value = false
        }
    }

    fun sendMessage(text: String) {
        if (text.isBlank()) return
        
        viewModelScope.launch {
            val currentList = _messages.value.toMutableList()
            currentList.add(HistoryItem("user", text))
            _messages.value = currentList
            _crisisAlert.value = null
            
            _isLoading.value = true
            when(val res = repository.sendMessage(text)) {
                is Resource.Success -> {
                    val updated = _messages.value.toMutableList()
                    updated.add(HistoryItem("assistant", res.data?.response ?: ""))
                    _messages.value = updated
                    
                    if (res.data?.emergency_contact != null) {
                        _crisisAlert.value = res.data.emergency_contact
                    }
                }
                is Resource.Error -> _error.value = res.message
                else -> {}
            }
            _isLoading.value = false
        }
    }
}
"""

files[f"{pkg}/ui/chat/ChatScreen.kt"] = """package com.psikochat.app.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.repository.ChatRepository
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repo = ChatRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ChatViewModel(repo) as T
        }
    }
    val viewModel: ChatViewModel = viewModel(factory = factory)
    
    val messages by viewModel.messages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()
    val crisisAlert by viewModel.crisisAlert.collectAsState()
    
    var inputText by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    
    LaunchedEffect(Unit) {
        viewModel.loadHistory()
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Psikochat-AI") },
                actions = {
                    TextButton(onClick = {
                        scope.launch {
                            tokenManager.clearToken()
                            navController.navigate("login") { popUpTo("chat") { inclusive = true } }
                        }
                    }) {
                        Text("Çıkış", color = MaterialTheme.colorScheme.error)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkSurface)
            )
        },
        bottomBar = {
            Surface(color = DarkSurface, modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.padding(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Mesajınızı yazın...") },
                        colors = OutlinedTextFieldDefaults.colors(
                            unfocusedContainerColor = DarkBackground,
                            focusedContainerColor = DarkBackground
                        )
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    IconButton(
                        onClick = {
                            viewModel.sendMessage(inputText)
                            inputText = ""
                        },
                        colors = IconButtonDefaults.iconButtonColors(containerColor = AccentPrimary)
                    ) {
                        Icon(Icons.Default.Send, contentDescription = "Gönder", tint = Color.White)
                    }
                }
            }
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            if (crisisAlert != null) {
                Surface(color = DangerRed.copy(alpha = 0.2f), modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = "Acil Durum: $crisisAlert",
                        color = DangerRed,
                        modifier = Modifier.padding(16.dp)
                    )
                }
            }
            
            if (error != null) {
                Text(text = error!!, color = DangerRed, modifier = Modifier.padding(16.dp))
            }
            
            LazyColumn(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(16.dp),
                reverseLayout = false
            ) {
                items(messages) { msg ->
                    MessageBubble(msg)
                    Spacer(modifier = Modifier.height(8.dp))
                }
                if (isLoading) {
                    item {
                        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                            CircularProgressIndicator()
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MessageBubble(msg: HistoryItem) {
    val isUser = msg.role == "user"
    val bgColor = if (isUser) AccentPrimary.copy(alpha=0.85f) else SystemChatBubble.copy(alpha=0.85f)
    val align = if (isUser) Alignment.CenterEnd else Alignment.CenterStart
    val shape = if (isUser) RoundedCornerShape(16.dp, 16.dp, 0.dp, 16.dp) else RoundedCornerShape(16.dp, 16.dp, 16.dp, 0.dp)
    
    Box(contentAlignment = align, modifier = Modifier.fillMaxWidth()) {
        Surface(
            color = bgColor,
            shape = shape,
            modifier = Modifier.widthIn(max = 280.dp)
        ) {
            Text(
                text = msg.text,
                color = Color.White,
                modifier = Modifier.padding(12.dp)
            )
        }
    }
}
"""

for rel_path, content in files.items():
    abs_path = os.path.join(BASE_DIR, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
print(f"Bitti. {len(files)} dosya oluturuldu.")
