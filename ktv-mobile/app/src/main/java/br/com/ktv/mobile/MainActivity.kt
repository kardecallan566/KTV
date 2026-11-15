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
   NavigationBar(containerColor = SurfaceDark) {
    NavigationBarItem(selectedTab == 0, { selectedTab = 0; selectedChannel = null }, icon = { Icon(Icons.Default.LiveTv, null) }, label = { Text("Canais") })
    NavigationBarItem(selectedTab == 1, { selectedTab = 1; selectedChannel = null }, icon = { Icon(Icons.Default.Favorite, null) }, label = { Text("Favoritos") })
    NavigationBarItem(selectedTab == 2, { selectedTab = 2; selectedChannel = null }, icon = { Icon(Icons.Default.Settings, null) }, label = { Text("Ajustes") })
   }
  }) { padding ->
   Column(Modifier.fillMaxSize().padding(padding).background(Brush.verticalGradient(listOf(Color(0xFF15152B), Background))).padding(horizontal = 20.dp)) {
    Row(Modifier.fillMaxWidth().padding(top = 18.dp, bottom = 14.dp), verticalAlignment = Alignment.CenterVertically) {
     Column(Modifier.weight(1f)) {
      Text("KTV", fontSize = 30.sp, fontWeight = FontWeight.Black, color = Color.White)
      Text("ENTRETENIMENTO SEM LIMITES", fontSize = 9.sp, color = TextMuted, letterSpacing = 2.sp)
     }
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
 Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
  OutlinedTextField(value = query, onValueChange = onQuery, modifier = Modifier.fillMaxWidth(), placeholder = { Text("Buscar canais…", color = TextMuted) }, leadingIcon = { Icon(Icons.Default.Search, null) }, singleLine = true, shape = RoundedCornerShape(16.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Accent, unfocusedBorderColor = Color(0xFF293044), focusedTextColor = Color.White, unfocusedTextColor = Color.White))
  Row(verticalAlignment = Alignment.CenterVertically) {
   Column(Modifier.weight(1f)) {
    Text("TV ao vivo", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold)
    Text(if (loading) "Atualizando listas…" else "${channels.size} canais disponíveis", color = TextMuted, fontSize = 12.sp)
   }
   IconButton(onClick = onReload, enabled = !loading) {
    if (loading) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
    else Icon(Icons.Default.Refresh, "Atualizar playlists", tint = Accent)
   }
  }
  LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(bottom = 2.dp)) {
   items(categories) { item -> FilterChip(selected = category == item, onClick = { onCategory(item) }, label = { Text(item, maxLines = 1) }) }
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
 Surface(color = SurfaceDark, shape = RoundedCornerShape(15.dp), modifier = Modifier.fillMaxWidth().clickable { onClick() }) {
  Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
   if (!channel.logo.isNullOrBlank()) {
    AsyncImage(model = channel.logo, contentDescription = channel.name, modifier = Modifier.size(46.dp), contentScale = androidx.compose.ui.layout.ContentScale.Fit)
   } else {
    Box(Modifier.size(46.dp).background(Color(0xFF272442), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) { Icon(Icons.Default.LiveTv, null, tint = Accent) }
   }
   Spacer(Modifier.width(12.dp))
   Column(Modifier.weight(1f)) {
    Text(channel.name, color = Color.White, fontWeight = FontWeight.SemiBold, maxLines = 1)
    Text(channel.category, color = TextMuted, fontSize = 12.sp, maxLines = 1)
   }
   IconButton(onClick = onFavorite) { Icon(Icons.Default.Favorite, null, tint = if (favorite) Color(0xFFFF6B91) else TextMuted) }
   Surface(color = Color(0xFF3A1C29), shape = RoundedCornerShape(6.dp)) {
    Text("LIVE", color = Color(0xFFFF849A), fontSize = 9.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 7.dp, vertical = 5.dp))
   }
  }
 }
}

@Composable
private fun FavoritesScreen(channels: List<TvChannel>, onOpen: (TvChannel) -> Unit, onRemove: (TvChannel) -> Unit) {
 Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
  Text("Seus favoritos", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold)
  if (channels.isEmpty()) {
   Text("Toque no coração de um canal para salvá-lo aqui.", color = TextMuted)
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
 Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
  Text("Configurações", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Bold)
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
