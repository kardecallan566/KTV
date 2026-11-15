package br.com.ktv.mobile

data class TvChannel(
 val name: String,
 val streamUrl: String,
 val category: String = "Outros",
 val logo: String? = null,
 val tvgId: String? = null
)

object M3UParser {
 private val urlPattern = Regex("^(https?|rtmp|rtsp)://", RegexOption.IGNORE_CASE)

 fun parse(content: String): List<TvChannel> {
  val result = mutableListOf<TvChannel>()
  var name: String? = null
  var category = "Outros"
  var logo: String? = null
  var tvgId: String? = null

  content.removePrefix("\uFEFF").lineSequence().map { it.trim() }.forEach { line ->
   when {
    line.isBlank() -> Unit
    line.startsWith("#EXTINF", ignoreCase = true) -> {
     val metadata = line.substringAfter(':', "").substringBeforeLast(',', "")
     name = line.substringAfterLast(',').trim().ifBlank { null }
     category = attribute(metadata, "group-title")?.trim()?.ifBlank { null } ?: "Outros"
     logo = attribute(metadata, "tvg-logo")?.takeIf { it.isNotBlank() }
     tvgId = attribute(metadata, "tvg-id")?.takeIf { it.isNotBlank() }
    }
    line.startsWith("#") -> Unit
    urlPattern.containsMatchIn(line) -> {
     val cleanUrl = line.substringBefore('|').trim()
     result += TvChannel(
      name = name?.takeIf { it.isNotBlank() } ?: "Canal ${result.size + 1}",
      streamUrl = cleanUrl,
      category = category,
      logo = logo,
      tvgId = tvgId
     )
     name = null
     category = "Outros"
     logo = null
     tvgId = null
    }
   }
  }
  return result.distinctBy { it.streamUrl }
 }

 private fun attribute(source: String, key: String): String? {
  val pattern = Regex("""(?:^|\s)${Regex.escape(key)}=["']([^"']*)["']""", RegexOption.IGNORE_CASE)
  return pattern.find(source)?.groupValues?.getOrNull(1)
 }
}
