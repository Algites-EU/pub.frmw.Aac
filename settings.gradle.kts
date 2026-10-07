/* The single build-domain bootstrap; all initialization is compiled in gradleinit. */
buildscript {
    repositories {
        if (providers.gradleProperty("modustro.useMavenLocalForResolution")
                .orElse(providers.environmentVariable("MODUSTRO_USE_MAVEN_LOCAL_FOR_RESOLUTION"))
                .orNull.equals("true", ignoreCase = true)) mavenLocal()
        mavenCentral()
        maven { url = uri("https://dl.cloudsmith.io/public/algites/java-snapshots-pub/maven/") }
    }
    dependencies {
        classpath("eu.algites.pltf.modustro.builder:pub.gov.Algites_devops.build.modustro.builder.gradleinit:1.0-SNAPSHOT")
    }
}
apply(plugin = "eu.algites.pltf.modustro.builder.settings")
