package br.com.ktv.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cast
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.LiveTv
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

private const val DEFAULT_PLAYLIST = "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u"
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
 var channels by remember { mutableStateOf<List<TvChannel>>(emptyList()) }
 var loading by remember { mutableStateOf(false) }
 var playlistError by remember { mutableStateOf<String?>(null) }
 var selectedCategory by remember { mutableStateOf("Todos") }

 suspend fun loadPlaylist() {
  loading = true
  playlistError = null
  try {
   channels = withContext(Dispatchers.IO) {
    val connection = (URL(DEFAULT_PLAYLIST).openConnection() as HttpURLConnection).apply {
     connectTimeout = 15000; readTimeout = 25000; requestMethod = "GET"
     setRequestProperty("User-Agent", "KTV-Mobile/0.1")
    }
    try {
     if (connection.responseCode !in 200..299) error("HTTP ${connection.responseCode}")
     connection.inputStream.bufferedReader(Charsets.UTF_8).use { M3UParser.parse(it.readText()) }
    } finally { connection.disconnect() }
   }
   if (channels.isEmpty()) playlistError = "A playlist foi carregada, mas não contém streams válidos."
  } catch (e: Exception) {
   playlistError = "Não foi possível carregar a playlist. Verifique sua conexão e tente novamente."
  } finally { loading = false }
 }

 LaunchedEffect(Unit) { loadPlaylist() }

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
    when(selectedTab) {
     0 -> HomeScreen(query, { query = it }, channels, loading, playlistError, selectedCategory, { selectedCategory = it }, { loadPlaylist() }, castMessage)
     1 -> EmptyState()
     else -> SettingsScreen(castMessage) { castMessage = it }
    }
   }
  }
 }
}

@Composable
private fun HomeScreen(
 query: String, onQuery: (String) -> Unit, channels: List<TvChannel>, loading: Boolean, error: String?,
 category: String, onCategory: (String) -> Unit, onReload: () -> Unit, castMessage: String
) {
 val categories = remember(channels) { listOf("Todos") + channels.map { it.category }.distinct().sorted() }
 val filtered = remember(channels, query, category) {
  channels.filter { (category == "Todos" || it.category.equals(category, true)) && it.name.contains(query, true) }
 }
 Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
  OutlinedTextField(value = query, onValueChange = onQuery, modifier = Modifier.fillMaxWidth(), placeholder = { Text("Buscar canais…", color = TextMuted) }, leadingIcon = { Icon(Icons.Default.Search, null) }, singleLine = true, shape = RoundedCornerShape(16.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Accent, unfocusedBorderColor = Color(0xFF293044), focusedTextColor = Color.White, unfocusedTextColor = Color.White))
  Row(verticalAlignment = Alignment.CenterVertically) {
   Column(Modifier.weight(1f)) { Text("TV ao vivo", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold); Text(if (loading) "Atualizando lista…" else "${channels.size} canais disponíveis", color = TextMuted, fontSize = 12.sp) }
   IconButton(onClick = onReload, enabled = !loading) { if (loading) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp) else Icon(Icons.Default.Refresh, "Atualizar playlist", tint = Accent) }
  }
  LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(bottom = 2.dp)) {
   items(categories) { item -> FilterChip(selected = category == item, onClick = { onCategory(item) }, label = { Text(item, maxLines = 1) }) }
  }
  if (error != null) {
   Surface(color = Color(0xFF351B27), shape = RoundedCornerShape(14.dp)) { Column(Modifier.fillMaxWidth().padding(14.dp)) { Text(error, color = Color(0xFFFFB4C2), fontSize = 13.sp); Spacer(Modifier.height(8.dp)); Text("Tentar novamente", color = Color.White, modifier = Modifier.clickable { onReload() }) } }
  } else if (filtered.isEmpty() && !loading) {
   Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) { Text(if (channels.isEmpty()) "Carregando canais…" else "Nenhum canal encontrado.", color = TextMuted) }
  } else {
   LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(9.dp), contentPadding = PaddingValues(bottom = 16.dp)) {
    items(filtered, key = { it.streamUrl }) { channel ->
     ChannelRow(channel)
    }
   }
  }
  Text(castMessage, color = TextMuted, fontSize = 11.sp, modifier = Modifier.padding(bottom = 5.dp))
 }
}

@Composable
private fun ChannelRow(channel: TvChannel) {
 Surface(color = SurfaceDark, shape = RoundedCornerShape(15.dp), modifier = Modifier.fillMaxWidth()) {
  Row(Modifier.padding(13.dp), verticalAlignment = Alignment.CenterVertically) {
   Box(Modifier.size(42.dp).background(Color(0xFF272442), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) { Icon(Icons.Default.LiveTv, null, tint = Accent) }
   Spacer(Modifier.width(12.dp))
   Column(Modifier.weight(1f)) { Text(channel.name, color = Color.White, fontWeight = FontWeight.SemiBold, maxLines = 1); Text(channel.category, color = TextMuted, fontSize = 12.sp, maxLines = 1) }
   Surface(color = Color(0xFF3A1C29), shape = RoundedCornerShape(6.dp)) { Text("LIVE", color = Color(0xFFFF849A), fontSize = 9.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 7.dp, vertical = 5.dp)) }
  }
 }
}

@Composable private fun SettingsScreen(status: String, onStatus: (String) -> Unit) {
 Text("Conectar à TV", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(12.dp))
 Surface(color = SurfaceDark, shape = RoundedCornerShape(18.dp)) { Column(Modifier.fillMaxWidth().padding(18.dp)) { Icon(Icons.Default.Cast, null, tint = Accent, modifier = Modifier.size(32.dp)); Spacer(Modifier.height(12.dp)); Text("Transmitir para televisão", color = Color.White, fontWeight = FontWeight.SemiBold); Text("Chromecast / Google TV e dispositivos compatíveis serão adicionados nesta etapa.", color = TextMuted); Spacer(Modifier.height(14.dp)); Button(onClick = { onStatus("Transmissão ainda em desenvolvimento — etapa inicial.") }) { Text("Procurar dispositivos") }; Spacer(Modifier.height(8.dp)); Text(status, color = TextMuted, fontSize = 12.sp) } }
 Spacer(Modifier.height(20.dp)); Text("Sobre o KTV Mobile", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold); Text("Versão 0.2.0 • Playlist integrada", color = TextMuted)
}
@Composable private fun EmptyState() { Column(Modifier.fillMaxWidth().padding(top = 40.dp), horizontalAlignment = Alignment.CenterHorizontally) { Icon(Icons.Default.Favorite, null, tint = Accent, modifier = Modifier.size(48.dp)); Spacer(Modifier.height(12.dp)); Text("Seus favoritos", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Bold); Text("Favoritos serão habilitados em breve.", color = TextMuted) } }
