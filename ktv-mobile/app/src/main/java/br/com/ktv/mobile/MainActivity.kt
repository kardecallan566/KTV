package br.com.ktv.mobile

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.util.Log
import android.os.Bundle
import android.net.Uri
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
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.FullscreenExit
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
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.activity.compose.BackHandler
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.MimeTypes
import androidx.media3.common.Player
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.common.util.UnstableApi
import androidx.media3.cast.CastPlayer
import androidx.media3.cast.MediaRouteButtonFactory
import androidx.media3.cast.MediaRouteButtonViewProvider
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.mediarouter.app.MediaRouteButton
import coil.compose.AsyncImage
import com.yinnho.upnpcast.DLNACast
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

private object KtvDiagnostics {
 private const val TAG = "KTVPlayer"
 private val entries = ArrayDeque<String>()
 @Synchronized fun add(message: String, error: Throwable? = null) {
  val line = "${java.time.Instant.now()} | $message" + (error?.let { " | ${it.javaClass.simpleName}: ${it.message}" } ?: "")
  entries.addLast(line)
  while (entries.size > 250) entries.removeFirst()
  if (error != null) Log.e(TAG, message, error) else Log.i(TAG, message)
 }
 @Synchronized fun report(): String = buildString {
  appendLine("KTV Mobile diagnostics")
  appendLine("Android: ${android.os.Build.VERSION.RELEASE} (API ${android.os.Build.VERSION.SDK_INT})")
  appendLine("Device: ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}")
  appendLine("---- eventos recentes ----")
  entries.forEach { appendLine(it) }
 }
}
private fun shareDiagnostics(context: Context) {
 val intent = Intent(Intent.ACTION_SEND).apply {
  type = "text/plain"
  putExtra(Intent.EXTRA_SUBJECT, "KTV Mobile - relatório de diagnóstico")
  putExtra(Intent.EXTRA_TEXT, KtvDiagnostics.report())
 }
 runCatching { context.startActivity(Intent.createChooser(intent, "Enviar logs do KTV")) }
  .onFailure { KtvDiagnostics.add("Falha ao abrir compartilhamento de logs", it) }
}

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
 var castMessage by remember { mutableStateOf("Toque no ícone de transmissão para procurar dispositivos na mesma rede Wi-Fi.") }
 var isPlayerFullscreen by remember { mutableStateOf(false) }
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
   if (!isPlayerFullscreen) NavigationBar(containerColor = Color(0xFF0D1220), tonalElevation = 0.dp) {
    NavigationBarItem(selectedTab == 0, { selectedTab = 0; selectedChannel = null }, icon = { Icon(Icons.Default.LiveTv, null) }, label = { Text("Início") }, colors = NavigationBarItemDefaults.colors(selectedIconColor = Color.White, indicatorColor = Accent.copy(alpha = 0.32f), selectedTextColor = Color.White, unselectedIconColor = TextMuted, unselectedTextColor = TextMuted))
    NavigationBarItem(selectedTab == 1, { selectedTab = 1; selectedChannel = null }, icon = { Icon(Icons.Default.Favorite, null) }, label = { Text("Favoritos") }, colors = NavigationBarItemDefaults.colors(selectedIconColor = Color.White, indicatorColor = Accent.copy(alpha = 0.32f), selectedTextColor = Color.White, unselectedIconColor = TextMuted, unselectedTextColor = TextMuted))
    NavigationBarItem(selectedTab == 2, { selectedTab = 2; selectedChannel = null }, icon = { Icon(Icons.Default.Settings, null) }, label = { Text("Ajustes") }, colors = NavigationBarItemDefaults.colors(selectedIconColor = Color.White, indicatorColor = Accent.copy(alpha = 0.32f), selectedTextColor = Color.White, unselectedIconColor = TextMuted, unselectedTextColor = TextMuted))
   }
  }) { padding ->
   Column(Modifier.fillMaxSize().padding(padding).background(Brush.verticalGradient(listOf(Color(0xFF17172F), Color(0xFF0B1020), Background))).then(if (isPlayerFullscreen) Modifier else Modifier.padding(horizontal = 18.dp))) {
    if (!isPlayerFullscreen) Row(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 16.dp), verticalAlignment = Alignment.CenterVertically) {
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
     selectedChannel != null && selectedTab == 0 -> PlayerScreen(selectedChannel!!, isPlayerFullscreen, { isPlayerFullscreen = it }, { selectedChannel = null })
     selectedTab == 0 -> HomeScreen(query, { query = it }, channels, loading, playlistError, selectedCategory, { selectedCategory = it }, { scope.launch { loadPlaylist() } }, favorites, { toggleFavorite(it, favorites, prefs) { favorites = it } }, { selectedChannel = it })
     selectedTab == 1 -> FavoritesScreen(channels.filter { it.streamUrl in favorites }, { selectedTab = 0; selectedChannel = it }, { toggleFavorite(it, favorites, prefs) { favorites = it } })
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
 Surface(color = Color(0xFF28234D), shape = RoundedCornerShape(14.dp), border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF5147A8))) {
  Row(Modifier.height(48.dp).padding(start = 7.dp, end = 10.dp), verticalAlignment = Alignment.CenterVertically) {
   AndroidView(
    factory = { ctx ->
     val themedContext = android.view.ContextThemeWrapper(ctx, R.style.KtvMediaRouterTheme)
     runCatching {
      MediaRouteButton(themedContext).apply {
       MediaRouteButtonFactory.setUpMediaRouteButton(themedContext, this)
       contentDescription = "Abrir dispositivos para transmissão"
       isFocusable = true
       isClickable = true
      }
     }.getOrElse {
      android.widget.TextView(ctx).apply {
       text = "TV"
       gravity = android.view.Gravity.CENTER
       setTextColor(android.graphics.Color.WHITE)
       contentDescription = "Google Cast indisponível"
       isEnabled = false
      }
     }
    },
    modifier = Modifier.size(42.dp)
   )
   Spacer(Modifier.width(5.dp))
   Text("Transmitir", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold)
  }
 }
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
    Text("Toque no ícone de transmissão no topo do aplicativo para procurar Chromecast, Google TV e receptores compatíveis com Google Cast na mesma rede Wi-Fi.", color = TextMuted, fontSize = 13.sp)
    Text(castMessage, color = TextMuted, fontSize = 12.sp)
    CastRouteButton()
   }
  }
  Text("KTV Mobile • canais, favoritos e transmissão", color = TextMuted, fontSize = 12.sp)
 }
}

@OptIn(UnstableApi::class)
@Composable
private fun PlayerScreen(channel: TvChannel, isFullscreen: Boolean, onFullscreenChange: (Boolean) -> Unit, onBack: () -> Unit) {
 val context = LocalContext.current
 val activity = context as? Activity
 BackHandler(enabled = isFullscreen) { onFullscreenChange(false) }
 DisposableEffect(activity, isFullscreen) {
  val window = activity?.window
  val controller = window?.let { WindowInsetsControllerCompat(it, it.decorView) }
  if (isFullscreen) controller?.hide(WindowInsetsCompat.Type.systemBars()) else controller?.show(WindowInsetsCompat.Type.systemBars())
  onDispose { controller?.show(WindowInsetsCompat.Type.systemBars()) }
 }
 val appContext = context.applicationContext
 var playerError by remember(channel.streamUrl) { mutableStateOf<String?>(null) }
 var isBuffering by remember(channel.streamUrl) { mutableStateOf(true) }
 var dlnaDevices by remember { mutableStateOf<List<DLNACast.Device>>(emptyList()) }
 var showDlnaPicker by remember { mutableStateOf(false) }
 var dlnaSearching by remember { mutableStateOf(false) }
 var dlnaCasting by remember { mutableStateOf(false) }
 var dlnaMessage by remember { mutableStateOf<String?>(null) }
 val playerScope = rememberCoroutineScope()
 DisposableEffect(appContext) {
  DLNACast.init(appContext)
  onDispose { DLNACast.cleanup() }
 }

 val mediaItem = remember(channel.streamUrl, channel.name, channel.category, channel.logo) {
  val metadata = MediaMetadata.Builder()
   .setTitle(channel.name)
   .setArtist(channel.category.ifBlank { "TV ao vivo • KTV" })
   .setMediaType(MediaMetadata.MEDIA_TYPE_TV_CHANNEL)
   .apply { if (!channel.logo.isNullOrBlank()) setArtworkUri(Uri.parse(channel.logo)) }
   .build()
  MediaItem.Builder()
   .setUri(channel.streamUrl)
   .setMediaMetadata(metadata)
   .apply {
    val path = channel.streamUrl.substringBefore('?').lowercase()
    if (path.endsWith(".m3u8")) setMimeType(MimeTypes.APPLICATION_M3U8)
   }
   .build()
 }

 val localPlayer = remember(channel.streamUrl) {
  val httpFactory = DefaultHttpDataSource.Factory()
   .setUserAgent("KTV-Mobile/0.5.0")
   .setConnectTimeoutMs(15_000)
   .setReadTimeoutMs(30_000)
   .setAllowCrossProtocolRedirects(true)
  val dataSourceFactory = DefaultDataSource.Factory(appContext, httpFactory)
  val mediaSourceFactory = DefaultMediaSourceFactory(dataSourceFactory)

  ExoPlayer.Builder(appContext)
   .setMediaSourceFactory(mediaSourceFactory)
   .build()
   .apply {
    setHandleAudioBecomingNoisy(true)
    addListener(object : Player.Listener {
     override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
      val detail = error.cause?.localizedMessage
       ?.takeIf { it.isNotBlank() }
       ?: error.localizedMessage
       ?: error.errorCodeName
      playerError = "Não foi possível reproduzir este canal. $detail".take(260)
      isBuffering = false
     }

     override fun onPlaybackStateChanged(playbackState: Int) {
      isBuffering = playerError == null &&
       (playbackState == Player.STATE_BUFFERING || playbackState == Player.STATE_IDLE)
      if (playbackState == Player.STATE_READY) playerError = null
     }
    })
    setMediaItem(mediaItem)
    prepare()
    playWhenReady = true
   }
 }

 // Se o Google Play Services/Cast falhar, o player local continua funcionando.
 val castPlayer = remember(localPlayer) {
  try {
   CastPlayer.Builder(context).setLocalPlayer(localPlayer).build()
  } catch (_: RuntimeException) {
   null
  }
 }
 val playbackPlayer: Player = castPlayer ?: localPlayer

 DisposableEffect(castPlayer, localPlayer) {
  onDispose {
   if (castPlayer != null) castPlayer.release() else localPlayer.release()
  }
 }

 if (isFullscreen) {
  Box(Modifier.fillMaxSize().background(Color.Black), contentAlignment = Alignment.Center) {
   AndroidView(
    factory = { ctx -> PlayerView(ctx).apply {
     this.player = playbackPlayer
     useController = true
     setShowBuffering(PlayerView.SHOW_BUFFERING_NEVER)
     setMediaRouteButtonViewProvider(MediaRouteButtonViewProvider())
     keepScreenOn = true
    } },
    update = { it.player = playbackPlayer },
    modifier = Modifier.fillMaxSize()
   )
   if (isBuffering && playerError == null) CircularProgressIndicator(color = Accent, modifier = Modifier.size(38.dp), strokeWidth = 3.dp)
   IconButton(onClick = { onFullscreenChange(false) }, modifier = Modifier.align(Alignment.TopEnd).padding(16.dp).background(Color(0x99000000), RoundedCornerShape(14.dp))) {
    Icon(Icons.Default.FullscreenExit, "Sair da tela cheia", tint = Color.White)
   }
   if (playerError != null) Surface(color = Color(0xEE351B27), shape = RoundedCornerShape(14.dp), modifier = Modifier.align(Alignment.BottomCenter).padding(18.dp)) {
    Text(playerError!!, color = Color.White, fontSize = 12.sp, modifier = Modifier.padding(12.dp))
   }
  }
 } else Column(Modifier.fillMaxSize().background(Background).padding(bottom = 10.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
  Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
   Text("‹  Voltar aos canais", color = Color.White, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f).clickable { onBack() }.padding(vertical = 12.dp))
   Surface(color = Color(0xFF1C2340), shape = RoundedCornerShape(12.dp)) {
    Row(Modifier.padding(horizontal = 10.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
     Box(Modifier.size(7.dp).background(Color(0xFFFF5368), RoundedCornerShape(50)))
     Spacer(Modifier.width(6.dp))
     Text("AO VIVO", color = Color(0xFFFFA1AE), fontSize = 10.sp, fontWeight = FontWeight.ExtraBold)
    }
   }
  }
  Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
   Text("ASSISTINDO AGORA", color = Color(0xFFA5A0FF), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
   Text(channel.name, color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, maxLines = 2)
   Text(channel.category.ifBlank { "Televisão ao vivo" }, color = TextMuted, fontSize = 13.sp)
  }
  Surface(color = Color.Black, shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth(), border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF293044))) {
   Box(Modifier.fillMaxWidth().aspectRatio(16f / 9f), contentAlignment = Alignment.Center) {
    AndroidView(
     factory = { ctx -> PlayerView(ctx).apply {
      this.player = playbackPlayer
      useController = true
      setShowBuffering(PlayerView.SHOW_BUFFERING_NEVER)
      setMediaRouteButtonViewProvider(MediaRouteButtonViewProvider())
      keepScreenOn = true
     } },
     update = { it.player = playbackPlayer },
     modifier = Modifier.fillMaxSize()
    )
    if (isBuffering && playerError == null) CircularProgressIndicator(color = Accent, modifier = Modifier.size(34.dp), strokeWidth = 3.dp)
    IconButton(onClick = { onFullscreenChange(true) }, modifier = Modifier.align(Alignment.BottomEnd).padding(10.dp).background(Color(0x99000000), RoundedCornerShape(12.dp))) {
     Icon(Icons.Default.Fullscreen, "Assistir em tela cheia", tint = Color.White)
    }
   }
  }
  Surface(color = Color(0xFF151C2D), shape = RoundedCornerShape(14.dp), border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF293044))) {
   Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
    Icon(Icons.Default.Cast, null, tint = Color(0xFFA5A0FF))
    Spacer(Modifier.width(8.dp))
    Column(Modifier.weight(1f)) {
     Text("Smart TV (DLNA)", color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
     Text("Samsung, LG e TVs compatíveis na mesma rede", color = TextMuted, fontSize = 10.sp)
    }
    OutlinedButton(enabled = !dlnaSearching && !dlnaCasting, onClick = {
     playerScope.launch {
      dlnaSearching = true
      dlnaMessage = "Procurando TVs na rede Wi-Fi…"
      try {
       dlnaDevices = DLNACast.search(timeout = 6000)
       showDlnaPicker = true
       dlnaMessage = if (dlnaDevices.isEmpty()) "Nenhuma TV DLNA encontrada. Verifique se celular e TV estão na mesma rede e se o DLNA está ativado." else null
      } catch (e: Exception) {
       dlnaMessage = "Falha ao procurar TVs: ${e.message ?: "erro de rede"}"
      } finally { dlnaSearching = false }
     }
    }) {
     if (dlnaSearching) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
     else Text("Buscar TV", fontSize = 11.sp)
    }
   }
  }
  if (dlnaCasting) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Accent)
  if (dlnaMessage != null) Text(dlnaMessage!!, color = if (dlnaMessage!!.startsWith("Reproduzindo")) Color(0xFF9BE7B1) else TextMuted, fontSize = 11.sp)
  if (showDlnaPicker) AlertDialog(
   onDismissRequest = { showDlnaPicker = false },
   title = { Text("Escolher Smart TV", color = Color.White) },
   text = {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
     if (dlnaDevices.isEmpty()) Text(dlnaMessage ?: "Nenhum dispositivo DLNA encontrado.", color = TextMuted)
     else dlnaDevices.forEach { device ->
      OutlinedButton(
       modifier = Modifier.fillMaxWidth(),
       enabled = !dlnaCasting,
       onClick = {
        showDlnaPicker = false
        playerScope.launch {
         dlnaCasting = true
         dlnaMessage = "Conectando a ${device.name}…"
         try {
          val sent = DLNACast.castToDevice(device, channel.streamUrl, channel.name)
          dlnaMessage = if (sent) "Reproduzindo em ${device.name}. O vídeo agora é enviado diretamente à TV." else "A TV ${device.name} não aceitou este stream. Ela pode não suportar o formato/URL."
         } catch (e: Exception) {
          dlnaMessage = "Não foi possível transmitir para ${device.name}: ${e.message ?: "falha DLNA"}"
         } finally { dlnaCasting = false }
        }
       }
      ) { Text(device.name, color = Color.White); Spacer(Modifier.width(8.dp)); Text(device.address, color = TextMuted, fontSize = 10.sp) }
     }
    }
   },
   confirmButton = { TextButton(onClick = { showDlnaPicker = false }) { Text("Fechar") } },
   containerColor = SurfaceDark
  )
  if (playerError != null) {
   Surface(color = Color(0xFF351B27), shape = RoundedCornerShape(15.dp)) {
    Column(Modifier.fillMaxWidth().padding(15.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
     Text("Falha na transmissão", color = Color(0xFFFFB4C2), fontWeight = FontWeight.Bold)
     Text(playerError!!, color = Color(0xFFFFCDD5), fontSize = 12.sp)
     OutlinedButton(onClick = {
      playerError = null
      isBuffering = true
      localPlayer.stop()
      localPlayer.setMediaItem(mediaItem)
      localPlayer.prepare()
      localPlayer.playWhenReady = true
     }) {
      Icon(Icons.Default.Refresh, null)
      Spacer(Modifier.width(7.dp))
      Text("Tentar novamente")
     }
    }
   }
  } else {
   Surface(color = Color(0xFF131B2B), shape = RoundedCornerShape(15.dp), border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF222C42))) {
    Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
     Box(Modifier.size(42.dp).background(Color(0xFF202944), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) {
      if (!channel.logo.isNullOrBlank()) AsyncImage(model = channel.logo, contentDescription = channel.name, modifier = Modifier.size(34.dp), contentScale = androidx.compose.ui.layout.ContentScale.Fit)
      else Icon(Icons.Default.LiveTv, null, tint = Color(0xFFA5A0FF))
     }
     Spacer(Modifier.width(12.dp))
     Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
      Text("Transmissão ao vivo", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
      Text("Reprodução pelo KTV Mobile", color = TextMuted, fontSize = 11.sp)
     }
     Text("KTV", color = Color(0xFFA5A0FF), fontSize = 16.sp, fontWeight = FontWeight.Black)
    }
   }
  }
 }
}
