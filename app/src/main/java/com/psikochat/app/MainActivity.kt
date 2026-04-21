package com.psikochat.app

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
import com.psikochat.app.ui.auth.RegistrationScreen
import com.psikochat.app.ui.auth.ForgotPasswordScreen
import com.psikochat.app.ui.home.HomeScreen
import com.psikochat.app.ui.home.ProfileScreen
import com.psikochat.app.ui.home.SettingsScreen
import com.psikochat.app.ui.home.TherapyScreen
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
                        composable("register") { RegistrationScreen(navController, tokenManager) }
                        composable("forgot_password") { ForgotPasswordScreen(navController) }
                        composable("home") { HomeScreen(navController, tokenManager) }
                        composable("profile") { ProfileScreen(navController, tokenManager) }
                        composable("settings") { SettingsScreen(navController, tokenManager) }
                        composable("therapy") { TherapyScreen(navController, tokenManager) }
                        composable("chat") { ChatScreen(navController, tokenManager) }
                    }
                }
            }
        }
    }
}
