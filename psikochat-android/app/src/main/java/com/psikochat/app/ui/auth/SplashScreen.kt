package com.psikochat.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.ui.theme.LoginBackground
import com.psikochat.app.ui.theme.LoginButton
import kotlinx.coroutines.flow.first

@Composable
fun SplashScreen(navController: NavController, tokenManager: TokenManager) {
    LaunchedEffect(Unit) {
        val token = tokenManager.getToken().first()
        if (!token.isNullOrEmpty()) {
            var role = tokenManager.getRole().first()
            if (role.isNullOrEmpty()) {
                try {
                    val api = RetrofitClient.create(tokenManager)
                    val profile = api.getProfile()
                    role = profile.role ?: "user"
                    tokenManager.saveRole(role)
                } catch (e: Exception) {
                    role = "user"
                }
            }

            if (role == "psychologist") {
                navController.navigate("psychologist_graph") { popUpTo("splash") { inclusive = true } }
            } else {
                val completed = tokenManager.isOnboardingCompleted().first()
                if (!completed) {
                    navController.navigate("onboarding_wizard") { popUpTo("splash") { inclusive = true } }
                } else {
                    navController.navigate("main_graph") { popUpTo("splash") { inclusive = true } }
                }
            }
        } else {
            navController.navigate("auth_graph") { popUpTo("splash") { inclusive = true } }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(LoginBackground),
        contentAlignment = Alignment.Center
    ) {
        CircularProgressIndicator(color = LoginButton)
    }
}
