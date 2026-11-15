package br.com.ktv.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cast
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.LiveTv
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val Background = Color(0xFF080B14)
private val SurfaceDark = Color(0xFF111827)
private val Accent = Color(0xFF6C63FF)
private val TextMuted = Color(0xFF9CA3AF)

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); setContent { KtvMobileApp() } }
}

@Composable
fun KtvMobileApp() {
 var selectedTab by remember { mutableIntStateOf(0) }
 var query by remember { mutableStateOf("") }
 var castMessage by remember { mutableStateOf("Nenhuma TV conectada") }
 MaterialTheme(colorScheme = darkColorScheme(primary = Accent, background = Background, surface = SurfaceDark)) {
  Scaffold(containerColor = Background, bottomBar = {
   NavigationBar(containerColor = SurfaceDark) {
    NavigationBarItem(selectedTab == 0, { selectedTab = 0 }, icon = { Icon(Icons.Default.LiveTv, null) }, label = { Text("Início") })
    NavigationBarItem(selectedTab == 1, { selectedTab = 1 }, icon = { Icon(Icons.Default.Favorite, null) }, label = { Text("Favoritos") })
    NavigationBarItem(selectedTab == 2, { selectedTab = 2 }, icon = { Icon(Icons.Default.Settings, null) }, label = { Text("Ajustes") })
   }
  }) { padding ->
   Column(Modifier.fillMaxSize().padding(padding).background(Brush.verticalGradient(listOf(Color(0xFF15152B), Background))).padding(horizontal = 20.dp)) {
    Row(Modifier.fillMaxWidth().padding(top = 22.dp, bottom = 18.dp), verticalAlignment = Alignment.CenterVertically) {
     Column(Modifier.weight(1f)) { Text("KTV", fontSize = 30.sp, fontWeight = FontWeight.Black, color = Color.White); Text("ENTRETENIMENTO SEM LIMITES", fontSize = 9.sp, color = TextMuted, letterSpacing = 2.sp) }
     IconButton(onClick = { castMessage = "A conexão será ativada em uma próxima etapa"; selectedTab = 2 }) { Icon(Icons.Default.Cast, "Transmitir", tint = Color.White) }
    }
    when(selectedTab) { 0 -> HomeScreen(query, { query = it }, castMessage); 1 -> EmptyState(); else -> SettingsScreen(castMessage) { castMessage = it } }
   }
  }
 }
}

@Composable
private fun HomeScreen(query: String, onQuery: (String) -> Unit, castMessage: String) {
 Column(verticalArrangement = Arrangement.spacedBy(18.dp)) {
  OutlinedTextField(value = query, onValueChange = onQuery, modifier = Modifier.fillMaxWidth(), placeholder = { Text("Buscar canais, filmes…", color = TextMuted) }, leadingIcon = { Icon(Icons.Default.Search, null) }, singleLine = true, shape = RoundedCornerShape(16.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Accent, unfocusedBorderColor = Color(0xFF293044), focusedTextColor = Color.White, unfocusedTextColor = Color.White))
  Box(Modifier.fillMaxWidth().height(190.dp).background(Brush.linearGradient(listOf(Color(0xFF342C75), Color(0xFF151B35))), RoundedCornerShape(24.dp)).padding(20.dp)) {
   Column(Modifier.align(Alignment.CenterStart)) { Text("SUA TV.", color = Color.White, fontSize = 27.sp, fontWeight = FontWeight.Bold); Text("Seu jeito. Em qualquer lugar.", color = Color(0xFFD4D2FF)); Spacer(Modifier.height(14.dp)); Surface(color = Accent, shape = RoundedCornerShape(50.dp)) { Text("EXPLORAR", modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp), color = Color.White, fontWeight = FontWeight.Bold) } }
  }
  Row(verticalAlignment = Alignment.CenterVertically) { Text("TV ao vivo", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f)); Text("Ver tudo", color = Color(0xFFA8A3FF), fontSize = 13.sp) }
  LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp)) { items(listOf("Esportes", "Filmes", "Notícias", "Infantil", "Música")) { category -> Surface(color = SurfaceDark, shape = RoundedCornerShape(50.dp)) { Text(category, color = Color.White, modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) } } }
  Row(verticalAlignment = Alignment.CenterVertically) { Surface(color = Color(0xFFEF4444), shape = RoundedCornerShape(6.dp)) { Text(" AO VIVO ", color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(5.dp)) }; Spacer(Modifier.width(8.dp)); Text("Pronto para conectar sua playlist", color = TextMuted, fontSize = 13.sp) }
  Text(castMessage, color = TextMuted, fontSize = 12.sp)
 }
}
@Composable private fun SettingsScreen(status: String, onStatus: (String) -> Unit) {
 Text("Conectar à TV", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(12.dp))
 Surface(color = SurfaceDark, shape = RoundedCornerShape(18.dp)) { Column(Modifier.fillMaxWidth().padding(18.dp)) { Icon(Icons.Default.Cast, null, tint = Accent, modifier = Modifier.size(32.dp)); Spacer(Modifier.height(12.dp)); Text("Transmitir para televisão", color = Color.White, fontWeight = FontWeight.SemiBold); Text("Chromecast / Google TV e dispositivos compatíveis serão adicionados nesta etapa.", color = TextMuted); Spacer(Modifier.height(14.dp)); Button(onClick = { onStatus("Transmissão ainda em desenvolvimento — etapa inicial.") }) { Text("Procurar dispositivos") }; Spacer(Modifier.height(8.dp)); Text(status, color = TextMuted, fontSize = 12.sp) } }
 Spacer(Modifier.height(20.dp)); Text("Sobre o KTV Mobile", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold); Text("Versão 0.1.0 • Protótipo inicial", color = TextMuted)
}
@Composable private fun EmptyState() { Column(Modifier.fillMaxWidth().padding(top = 40.dp), horizontalAlignment = Alignment.CenterHorizontally) { Icon(Icons.Default.Favorite, null, tint = Accent, modifier = Modifier.size(48.dp)); Spacer(Modifier.height(12.dp)); Text("Seus favoritos", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Bold); Text("Os canais favoritos aparecerão aqui.", color = TextMuted) } }
