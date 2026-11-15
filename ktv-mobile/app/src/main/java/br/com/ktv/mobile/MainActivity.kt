package br.com.ktv.mobile

import android.content.Context
import android.os.Bundle
import androidx.fragment.app.FragmentActivity
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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.cast.CastPlayer
import androidx.media3.cast.MediaRouteButtonFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.mediarouter.app.MediaRouteButton
import coil.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

private const val DEFAULT_PLAYLIST = "https://raw.githubusercontent.com/Kaiollio-cpu/iptv_free/refs/heads/main/main.m3u"
private const val PREFS = "ktv_mobile"
private const val KEY_PLAYLISTS = "playlist_urls"
private const val KEY_FAVORITES = "favorite_streams"
private val Background = Color(0xFF080B14)
private val SurfaceDark = Color(0xFF111827)
private val Accent = Color(0xFF6C63FF)
private val TextMuted = Color(0xFF9CA3AF)

class MainActivity : FragmentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)
  setContent { KtvMobileApp() }
 }
}

private fun preferences(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

@Composable
fun KtvMobileApp() {
 val context = LocalContext.current
 val prefs = remember { preferences(context) }
 var selectedTab by remember { mutableIntStateOf(0) }
 var selectedChannel by remember { mutableStateOf<TvChannel?>(null) }
 var query by remember { mutableStateOf("") }
 var channels by remember { mutableStateOf<List<TvChannel>>(emptyList()) }
 var loading by remember { mutableStateOf(false) }
 var playlistError by remember { mutableStateOf<String?>(null) }
 var selectedCategory by remember { mutableStateOf("Todos") }
 var playlistUrls by remember { mutableStateOf(prefs.getString(KEY_PLAYLISTS, DEFAULT_PLAYLIST) ?: DEFAULT_PLAYLIST) }
 var favorites by remember { mutableStateOf(prefs.getStringSet(KEY_FAVORITES, emptySet())?.toSet() ?: emptySet()) }
 var castMessage by remember { mutableStateOf("Use o ícone de transmissão para localizar TVs compatíveis na mesma rede Wi-Fi.") }
 val scope = rememberCoroutineScope()

 suspend fun loadPlaylist() {
  loading = true
  playlistError = null
  try {
   val urls = playlistUrls.lines().map { it.trim() }.filter { it.startsWith("https://") || it.startsWith("http://") }.distinct()
   if (urls.isEmpty()) error("Adicione ao menos uma URL HTTP ou HTTPS.")
   val loaded = withContext(Dispatchers.IO) {
    urls.flatMap { source ->
     runCatching {
      val connection = (URL(source).openConnection() as HttpURLConnection).apply {
       connectTimeout = 15000
       readTimeout = 30000
       instanceFollowRedirects = true
       requestMethod = "GET"
       setRequestProperty("User-Agent", "KTV-Mobile/0.3")
       setRequestProperty("Accept", "application/vnd.apple.mpegurl,audio/x-mpegurl,*/*")
      }
      try {
       if (connection.responseCode !in 200..299) error("HTTP ${connection.responseCode}")
       connection.inputStream.bufferedReader(Charsets.UTF_8).use { M3UParser.parse(it.readText()) }
      } finally { connection.disconnect() }
     }.getOrDefault(emptyList())
    }.distinctBy { it.streamUrl }
   }
   channels = loaded
   if (loaded.isEmpty()) playlistError = "Nenhum canal válido foi encontrado nas listas. Confira as URLs e tente novamente."
  } catch (e: Exception) {
   playlistError = e.message ?: "Não foi possível carregar as playlists."
  } finally { loading = false }
 }

 LaunchedEffect(Unit) { loadPlaylist() }

 MaterialTheme(colorScheme = darkColorScheme(primary = Accent, background = Background, surface = SurfaceDark)) {
  Scaffold(containerColor = Background, bottomBar = {
   NavigationBar(containerColor = Color(0xFF0D1220), tonalElevation = 0.dp) {
    NavigationBarItem(selectedTab == 0, { selectedTab = 0; selectedChannel = null }, icon = { Icon(Icons.Default.LiveTv, null) }, label = { Text("Início") }, colors = NavigationBarItemDefaults.colors(selectedIconColor = Color.White, indicatorColor = Accent.copy(alpha = 0.32f), selectedTextColor = Color.White, unselectedIconColor = TextMuted, unselectedTextColor = TextMuted))
    NavigationBarItem(selectedTab == 1, { selectedTab = 1; selectedChannel = null }, icon = { Icon(Icons.Default.Favorite, null) }, label = { Text("Favoritos") }, colors = NavigationBarItemDefaults.colors(selectedIconColor = Color.White, indicatorColor = Accent.copy(alpha = 0.32f), selectedTextColor = Color.White, unselectedIconColor = TextMuted, unselectedTextColor = TextMuted))
    NavigationBarItem(selectedTab == 2, { selectedTab = 2; selectedChannel = null }, icon = { Icon(Icons.Default.Settings, null) }, label = { Text("Ajustes") }, colors = NavigationBarItemDefaults.colors(selectedIconColor = Color.White, indicatorColor = Accent.copy(alpha = 0.32f), selectedTextColor = Color.White, unselectedIconColor = TextMuted, unselectedTextColor = TextMuted))
   }
  }) { padding ->
   Column(Modifier.fillMaxSize().padding(padding).background(Brush.verticalGradient(listOf(Color(0xFF17172F), Color(0xFF0B1020), Background))).padding(horizontal = 18.dp)) {
    Row(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 16.dp), verticalAlignment = Alignment.CenterVertically) {
     Column(Modifier.weight(1f)) {
      Text("KTV", fontSize = 32.sp, fontWeight = FontWeight.Black, color = Color.White, letterSpacing = (-1).sp)
      Text("SUA CENTRAL DE ENTRETENIMENTO", fontSize = 9.sp, color = TextMuted, letterSpacing = 1.5.sp)
     }
     Surface(color = Color(0xFF1C2340), shape = RoundedCornerShape(14.dp)) {
      Row(Modifier.padding(horizontal = 10.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
       Box(Modifier.size(7.dp).background(Color(0xFF4ADE80), RoundedCornerShape(50)))
       Spacer(Modifier.width(7.dp))
       Text("AO VIVO", color = Color(0xFFB9F6CA), fontSize = 10.sp, fontWeight = FontWeight.Bold)
      }
     }
     Spacer(Modifier.width(8.dp))
     CastRouteButton()
    }
    when {
     selectedChannel != null && selectedTab == 0 -> PlayerScreen(selectedChannel!!, { selectedChannel = null })
     selectedTab == 0 -> HomeScreen(query, { query = it }, channels, loading, playlistError, selectedCategory, { selectedCategory = it }, { scope.launch { loadPlaylist() } }, favorites, { toggleFavorite(it, favorites, prefs) { favorites = it } }, { selectedChannel = it })
     selectedTab == 1 -> FavoritesScreen(channels.filter { it.streamUrl in favorites }, { selectedChannel = it }, { toggleFavorite(it, favorites, prefs) { favorites = it } })
     else -> SettingsScreen(playlistUrls, { playlistUrls = it }, {
      prefs.edit().putString(KEY_PLAYLISTS, playlistUrls).apply()
      scope.launch { loadPlaylist() }
     }, castMessage)
    }
   }
  }
 }
}

private fun toggleFavorite(channel: TvChannel, current: Set<String>, prefs: android.content.SharedPreferences, update: (Set<String>) -> Unit) {
 val next = if (channel.streamUrl in current) current - channel.streamUrl else current + channel.streamUrl
 prefs.edit().putStringSet(KEY_FAVORITES, next).apply()
 update(next)
}

@Composable
private fun CastRouteButton() {
 val context = LocalContext.current
 AndroidView(
  factory = { ctx ->
   MediaRouteButton(ctx).apply {
    MediaRouteButtonFactory.setUpMediaRouteButton(context, this)
   }
  },
  modifier = Modifier.size(48.dp)
 )
}

@Composable
private fun HomeScreen(
 query: String, onQuery: (String) -> Unit, channels: List<TvChannel>, loading: Boolean, error: String?,
 category: String, onCategory: (String) -> Unit, onReload: () -> Unit,
 favorites: Set<String>, onFavorite: (TvChannel) -> Unit, onChannelClick: (TvChannel) -> Unit
) {
 val categories = remember(channels) { listOf("Todos") + channels.map { it.category }.distinct().sorted() }
 val filtered = remember(channels, query, category) {
  channels.filter { (category == "Todos" || it.category.equals(category, true)) && it.name.contains(query, true) }
 }
 Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
  Surface(color = Color(0xFF171D35), shape = RoundedCornerShape(20.dp)) {
   Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 15.dp), verticalAlignment = Alignment.CenterVertically) {
    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
     Text("EXPLORE", color = Color(0xFFA5A0FF), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
     Text("TV ao vivo", color = Color.White, fontSize = 23.sp, fontWeight = FontWeight.ExtraBold)
     Text(if (loading) "Sincronizando suas listas…" else "${channels.size} canais na sua programação", color = TextMuted, fontSize = 12.sp)
    }
    Box(Modifier.size(48.dp).background(Accent.copy(alpha = 0.18f), RoundedCornerShape(15.dp)), contentAlignment = Alignment.Center) {
     Icon(Icons.Default.LiveTv, null, tint = Color(0xFFA5A0FF), modifier = Modifier.size(26.dp))
    }
   }
  }
  OutlinedTextField(value = query, onValueChange = onQuery, modifier = Modifier.fillMaxWidth(), placeholder = { Text("Buscar canal ou programação…", color = TextMuted) }, leadingIcon = { Icon(Icons.Default.Search, null, tint = TextMuted) }, singleLine = true, shape = RoundedCornerShape(15.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Accent, unfocusedBorderColor = Color(0xFF293044), focusedTextColor = Color.White, unfocusedTextColor = Color.White, cursorColor = Accent))
  Row(verticalAlignment = Alignment.CenterVertically) {
   Text("Categorias", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
   IconButton(onClick = onReload, enabled = !loading) {
    if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
    else Icon(Icons.Default.Refresh, "Atualizar playlists", tint = Accent)
   }
  }
  
   LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(vertical = 2.dp)) {
   items(categories) { item -> FilterChip(selected = category == item, onClick = { onCategory(item) }, label = { Text(item, maxLines = 1, fontWeight = if (category == item) FontWeight.Bold else FontWeight.Normal) }, shape = RoundedCornerShape(12.dp), colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Accent, selectedLabelColor = Color.White, containerColor = Color(0xFF151C2D), labelColor = TextMuted)) }
  }
  Row(verticalAlignment = Alignment.CenterVertically) {
   Text("Canais disponíveis", color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
   Text("${filtered.size} resultados", color = TextMuted, fontSize = 11.sp)
  }
  if (error != null) {
   Surface(color = Color(0xFF351B27), shape = RoundedCornerShape(14.dp)) {
    Column(Modifier.fillMaxWidth().padding(14.dp)) {
     Text(error, color = Color(0xFFFFB4C2), fontSize = 13.sp)
     Spacer(Modifier.height(8.dp))
     Text("Tentar novamente", color = Color.White, modifier = Modifier.clickable { onReload() })
    }
   }
  } else if (filtered.isEmpty() && !loading) {
   Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
    Text(if (channels.isEmpty()) "Carregando canais…" else "Nenhum canal encontrado.", color = TextMuted)
   }
  } else {
   LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(9.dp), contentPadding = PaddingValues(bottom = 16.dp)) {
    items(filtered, key = { it.streamUrl }) { channel ->
     ChannelRow(channel, channel.streamUrl in favorites, { onFavorite(channel) }) { onChannelClick(channel) }
    }
   }
  }
 }
}

@Composable
private fun ChannelRow(channel: TvChannel, favorite: Boolean, onFavorite: () -> Unit, onClick: () -> Unit) {
 Surface(color = Color(0xFF131B2B), shape = RoundedCornerShape(17.dp), modifier = Modifier.fillMaxWidth().clickable { onClick() }, border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF222C42))) {
  Row(Modifier.padding(horizontal = 13.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
   Box(Modifier.size(52.dp).background(Color(0xFF202944), RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
    if (!channel.logo.isNullOrBlank()) {
     AsyncImage(model = channel.logo, contentDescription = channel.name, modifier = Modifier.size(42.dp), contentScale = androidx.compose.ui.layout.ContentScale.Fit)
    } else {
     Icon(Icons.Default.LiveTv, null, tint = Color(0xFFA5A0FF), modifier = Modifier.size(25.dp))
    }
   }
   Spacer(Modifier.width(13.dp))
   Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
    Text(channel.name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1)
    Text(channel.category.ifBlank { "TV • Ao vivo" }, color = TextMuted, fontSize = 11.sp, maxLines = 1)
   }
   Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(3.dp)) {
    IconButton(onClick = onFavorite, modifier = Modifier.size(38.dp)) { Icon(Icons.Default.Favorite, null, tint = if (favorite) Color(0xFFFF6B91) else Color(0xFF667085), modifier = Modifier.size(20.dp)) }
    Surface(color = Color(0xFF3A1C29), shape = RoundedCornerShape(6.dp)) {
     Text("LIVE", color = Color(0xFFFF91A6), fontSize = 8.sp, fontWeight = FontWeight.ExtraBold, modifier = Modifier.padding(horizontal = 7.dp, vertical = 4.dp))
    }
   }
  }
 }
}

@Composable
private fun FavoritesScreen(channels: List<TvChannel>, onOpen: (TvChannel) -> Unit, onRemove: (TvChannel) -> Unit) {
 Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
  Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
   Text("SUA SELEÇÃO", color = Color(0xFFA5A0FF), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
   Text("Seus favoritos", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.ExtraBold)
   Text("Seus canais salvos em um só lugar", color = TextMuted, fontSize = 12.sp)
  }
  if (channels.isEmpty()) {
   Surface(color = SurfaceDark, shape = RoundedCornerShape(18.dp)) {
    Column(Modifier.fillMaxWidth().padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
     Icon(Icons.Default.Favorite, null, tint = Color(0xFFFF6B91), modifier = Modifier.size(32.dp))
     Text("Sua lista está vazia", color = Color.White, fontWeight = FontWeight.Bold)
     Text("Toque no coração de um canal para salvá-lo aqui.", color = TextMuted, fontSize = 12.sp)
    }
   }
  } else {
   LazyColumn(verticalArrangement = Arrangement.spacedBy(9.dp)) {
    items(channels, key = { it.streamUrl }) { channel ->
     ChannelRow(channel, true, { onRemove(channel) }) { onOpen(channel) }
    }
   }
  }
 }
}

@Composable
private fun SettingsScreen(urls: String, onUrlsChange: (String) -> Unit, onSave: () -> Unit, castMessage: String) {
 Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
  Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
   Text("PERSONALIZE", color = Color(0xFFA5A0FF), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
   Text("Configurações", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.ExtraBold)
   Text("Gerencie suas fontes e conexões", color = TextMuted, fontSize = 12.sp)
  }
  Surface(color = SurfaceDark, shape = RoundedCornerShape(18.dp)) {
   Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
    Text("Playlists de canais", color = Color.White, fontWeight = FontWeight.SemiBold)
    Text("Informe uma URL M3U por linha. A lista padrão pode continuar junto com outras fontes.", color = TextMuted, fontSize = 12.sp)
    OutlinedTextField(value = urls, onValueChange = onUrlsChange, modifier = Modifier.fillMaxWidth(), minLines = 3, maxLines = 6, placeholder = { Text("https://exemplo.com/lista.m3u") }, colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Color.White, unfocusedTextColor = Color.White))
    Button(onClick = onSave, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.Refresh, null); Spacer(Modifier.width(8.dp)); Text("Salvar e carregar canais") }
   }
  }
  Surface(color = SurfaceDark, shape = RoundedCornerShape(18.dp)) {
   Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
    Row(verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.Cast, null, tint = Accent); Spacer(Modifier.width(8.dp)); Text("Transmissão pela rede Wi-Fi", color = Color.White, fontWeight = FontWeight.SemiBold) }
    Text("Use o botão de transmissão no topo para procurar Chromecast, Google TV e outros receptores compatíveis com Google Cast na mesma rede Wi-Fi.", color = TextMuted, fontSize = 13.sp)
    Text(castMessage, color = TextMuted, fontSize = 12.sp)
   }
  }
  Text("KTV Mobile • canais, favoritos e transmissão", color = TextMuted, fontSize = 12.sp)
 }
}

@OptIn(UnstableApi::class)
@Composable
private fun PlayerScreen(channel: TvChannel, onBack: () -> Unit) {
 val context = LocalContext.current
 var playerError by remember(channel.streamUrl) { mutableStateOf<String?>(null) }
 val localPlayer = remember(channel.streamUrl) {
  ExoPlayer.Builder(context).build().apply {
   addListener(object : androidx.media3.common.Player.Listener {
    override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
     playerError = "Não foi possível reproduzir este canal. A transmissão pode estar offline ou indisponível neste dispositivo."
    }
   })
   setMediaItem(MediaItem.fromUri(channel.streamUrl))
   prepare()
   playWhenReady = true
  }
 }
 val player = remember(localPlayer) { CastPlayer.Builder(context).setLocalPlayer(localPlayer).build() }
 DisposableEffect(localPlayer) { onDispose { localPlayer.release() } }
 Column(Modifier.fillMaxSize().background(Background).padding(12.dp)) {
  Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
   Text("‹  Voltar", color = Color.White, modifier = Modifier.weight(1f).clickable { onBack() }.padding(vertical = 12.dp))
   CastRouteButton()
  }
  Text(channel.name, color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Bold)
  Text(channel.category, color = TextMuted, modifier = Modifier.padding(bottom = 12.dp))
  AndroidView(factory = { ctx -> PlayerView(ctx).apply { this.player = player; useController = true } }, update = { it.player = player }, modifier = Modifier.fillMaxWidth().aspectRatio(16f / 9f))
  if (playerError != null) {
   Text(playerError!!, color = Color(0xFFFFB4C2), modifier = Modifier.padding(top = 12.dp))
  } else {
   Text("Reprodução ao vivo • KTV", color = TextMuted, fontSize = 12.sp, modifier = Modifier.padding(top = 12.dp))
  }
 }
}
