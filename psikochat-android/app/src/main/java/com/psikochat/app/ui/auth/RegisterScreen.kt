package com.psikochat.app.ui.auth

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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

@Composable
fun RegisterScreen(navController: NavController, tokenManager: TokenManager) {
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
    var confirmPassword by remember { mutableStateOf("") }
    var validationError by remember { mutableStateOf<String?>(null) }
    
    val authState by viewModel.authState.collectAsState()

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
        Text("Yeni Hesap Oluştur", style = MaterialTheme.typography.headlineLarge, color = MaterialTheme.colorScheme.primary)
        Spacer(modifier = Modifier.height(32.dp))

        OutlinedTextField(
            value = username, onValueChange = { username = it; validationError = null },
            label = { Text("Kullanıcı Adı") },
            modifier = Modifier.fillMaxWidth(),
            isError = validationError != null && username.isEmpty()
        )
        Spacer(modifier = Modifier.height(8.dp))
        
        OutlinedTextField(
            value = password, onValueChange = { password = it; validationError = null },
            label = { Text("Şifre") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
            isError = validationError != null && password.length < 6
        )
        Spacer(modifier = Modifier.height(8.dp))

        OutlinedTextField(
            value = confirmPassword, onValueChange = { confirmPassword = it; validationError = null },
            label = { Text("Şifreyi Onayla") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
            isError = validationError != null && confirmPassword != password
        )
        
        if (validationError != null) {
            Text(text = validationError!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }

        Spacer(modifier = Modifier.height(16.dp))

        if (authState is Resource.Loading) {
            CircularProgressIndicator()
        } else {
            Button(
                onClick = {
                    if (username.length < 3) {
                        validationError = "Kullanıcı adı en az 3 karakter olmalıdır."
                    } else if (password.length < 6) {
                        validationError = "Şifre en az 6 karakter olmalıdır."
                    } else if (password != confirmPassword) {
                        validationError = "Şifreler eşleşmiyor."
                    } else {
                        viewModel.register(username, password)
                    }
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Kayıt Ol")
            }
            
            TextButton(onClick = { navController.popBackStack() }) {
                Text("Zaten hesabın var mı? Giriş Yap")
            }
        }

        if (authState is Resource.Error) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(text = authState.message ?: "Hata", color = MaterialTheme.colorScheme.error)
        }
    }
}
