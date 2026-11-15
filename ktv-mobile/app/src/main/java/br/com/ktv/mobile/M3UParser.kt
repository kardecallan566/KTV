package br.com.ktv.mobile

data class TvChannel(val name: String, val streamUrl: String, val category: String = "Outros", val logo: String? = null, val tvgId: String? = null)

object M3UParser {
    fun parse(content: String): List<TvChannel> {
        val result = mutableListOf<TvChannel>()
        var name: String? = null
        var category = "Outros"
        var logo: String? = null
        var tvgId: String? = null
        content.lineSequence().map(String::trim).forEach { line ->
            when {
                line.isBlank() -> Unit
                line.startsWith("#EXTINF", ignoreCase = true) -> {
                    val metadata = line.substringBeforeLast(",", "").substringAfter("#EXTINF:", "")
                    name = line.substringAfterLast(",", "").trim().ifBlank { "Canal ${result.size + 1}" }
                    category = attribute(metadata, "group-title")?.trim()?.ifBlank { null } ?: "Outros"
                    logo = attribute(metadata, "tvg-logo")
                    tvgId = attribute(metadata, "tvg-id")
                }
                line.startsWith("#") -> Unit
                line.startsWith("http://", true) || line.startsWith("https://", true) -> {
                    result += TvChannel(name = name?.takeIf(String::isNotBlank) ?: "Canal ${result.size + 1}", streamUrl = line, category = category, logo = logo, tvgId = tvgId)
                    name = null; category = "Outros"; logo = null; tvgId = null
                }
            }
        }
        return result.distinctBy { it.streamUrl }
    }
    private fun attribute(source: String, key: String): String? {
        val regex = Regex("""(?:^|\\s)${Regex.escape(key)}="([^"]*)"""", RegexOption.IGNORE_CASE)
        return regex.find(source)?.groupValues?.getOrNull(1)
    }
}
