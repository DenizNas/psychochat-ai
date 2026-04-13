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
                OutlinedButton(onClick = { navController.navigate("register") }, modifier = Modifier.weight(1f)) {
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
