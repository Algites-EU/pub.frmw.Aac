// Reuse the generator dependencies already resolved by Modustro. Applied Kotlin
// scripts have separate compile classpaths, so hand the JVM task the owning jars.
val locSchemaGeneratorLoaders = rootProject.subprojects.mapNotNull {
    it.tasks.findByName("generateModustroDefinitionSources")?.javaClass?.classLoader
} + listOf(rootProject.buildscript.classLoader)
val locSchemaGeneratorClasses = listOf(
    "eu.algites.tool.codegen.defs.AIcDefaultDefsCodegenService",
    "eu.algites.tool.codegen.defs.AIcdCodeGenerationRequest",
    "eu.algites.lib.naming.convention.AIcAlgitesNamingProfiles",
    "eu.algites.lib.naming.convention.AIcdNamingProfile",
    "eu.algites.lib.naming.conversion.AIcDefaultNameConverter",
    "eu.algites.lib.naming.conversion.AIiNameConverter",
    "com.fasterxml.jackson.databind.ObjectMapper",
    "com.fasterxml.jackson.core.JsonFactory",
    "com.fasterxml.jackson.annotation.JsonProperty",
    "com.fasterxml.jackson.dataformat.yaml.YAMLFactory",
    "org.yaml.snakeyaml.Yaml"
)
val locSchemaGeneratorClasspath = locSchemaGeneratorClasses.map { name ->
    val type = locSchemaGeneratorLoaders.firstNotNullOfOrNull { loader ->
        try { Class.forName(name, false, loader) } catch (failure: ClassNotFoundException) { null }
    } ?: throw GradleException("Modustro's generator classpath is missing $name.")
    java.io.File(type.protectionDomain.codeSource.location.toURI())
}.distinct()
val locGenerateSchemaBindings = rootProject.tasks.register<JavaExec>("generateModustroSchemaBindings") {
    group = "modustro"
    description = "Generates schema contracts in coreintf and implementations in coreimpl."
    classpath = files(locSchemaGeneratorClasspath)
    mainClass.set("eu.algites.tool.codegen.defs.AIcSchemaObjectBindingsGenerator")
    args(rootProject.projectDir.absolutePath, rootProject.file("devtools/schema-field-bindings.json").absolutePath)
    inputs.file(rootProject.file("devtools/schema-field-bindings.json"))
    inputs.files(rootProject.fileTree("aac/coreintf/src/product") {
        include("jsondefs/**/*.jsondef.schema.json", "yamldefs/**/*.yamldef.schema.json")
    })
    // Shared .gen roots are not exclusive outputs. General prunes only its recorded files.
    outputs.upToDateWhen { false }
}
rootProject.subprojects {
    if (projectDir == rootProject.file("aac/coreintf")) {
        tasks.matching { it.name == "generateModustroDefinitionSources" }.configureEach {
            // The repository task also handles every nested object and separates contracts from DTOs.
            onlyIf { false }
            dependsOn(locGenerateSchemaBindings)
        }
    }
    if (projectDir in listOf(rootProject.file("aac/coreintf"), rootProject.file("aac/coreimpl"))) {
        tasks.matching {
            it.name in setOf("processModustroJavaNativeSources", "processModustroPythonNativeSources",
                "compileJava", "compileTestJava", "test", "buildPython", "preparePythonBuildProject",
                "prepareModustroPythonDevelopBuildProject", "generatePythonProjectMetadata", "stageModustroPythonPackageResources") || it.name.startsWith("testModustroPython")
        }.configureEach { dependsOn(locGenerateSchemaBindings) }
    }
}

val locSchemaBindingsTest = rootProject.tasks.register<Exec>("testModustroSchemaBindings") {
    group = "verification"
    description = "Tests freshly generated Python contracts, implementations and schema package paths."
    dependsOn(locGenerateSchemaBindings)
    workingDir(rootProject.projectDir)
    environment("PYTHONPYCACHEPREFIX", rootProject.file("build/run/schema-bindings/pycache").absolutePath)
    commandLine(System.getenv("ALGITES_PYTHON_EXECUTABLE") ?: "python3", rootProject.file("devtools/test_schema_bindings.py").absolutePath)
}
rootProject.tasks.matching { it.name in setOf("test", "check") }.configureEach { dependsOn(locSchemaBindingsTest) }
rootProject.subprojects {
    tasks.matching { it.name in setOf("test", "check") }.configureEach { dependsOn(locSchemaBindingsTest) }
}
// Python-only repositories have no native Gradle Test tasks. Supply the standard CI entry point.
if (rootProject.tasks.findByName("test") == null) {
    rootProject.tasks.register("test") {
        group = "verification"
        dependsOn(locSchemaBindingsTest)
        dependsOn(rootProject.subprojects.flatMap { project -> project.tasks.matching { it.name == "test" }.toList() })
    }
}

rootProject.tasks.matching { it.name == "validateModustroPythonDistributionPaths" }.configureEach {
    dependsOn(locGenerateSchemaBindings)
}
val locSchemaCleanTasks = rootProject.allprojects.filter { "clean" in it.tasks.names }.map { it.tasks.named("clean") }
locGenerateSchemaBindings.configure { mustRunAfter(locSchemaCleanTasks) }
