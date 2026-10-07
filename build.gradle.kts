val locModustroRootBuildScript = file("gradle/tool/repository/modustro-root-build.gradle.kts")
if (locModustroRootBuildScript.isFile) {
    apply(from = locModustroRootBuildScript)
} else {
    apply(from = uri("https://raw.githubusercontent.com/Algites-EU/pub.gov.Algites/${System.getenv("MODUSTRO_PUBLIC_GOVERNANCE_REVISION") ?: "main"}/gradle/tool/repository/modustro-root-build.gradle.kts"))
}
