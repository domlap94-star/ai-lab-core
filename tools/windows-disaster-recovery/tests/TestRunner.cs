using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using NextStabil.Recovery;

public static class TestRunner
{
    private static int passed;
    private static int failed;

    public static int RunAll()
    {
        var root = Path.Combine(Path.GetTempPath(), "next-recovery-tests-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            Run("valid_database_checkpoint", delegate { var p = CreateCheckpoint(root, false, false); var r = new CheckpointValidator().Validate(p, null); Assert(r.Valid && r.DatabaseEligible && !r.FullEligible, r.ErrorCode); });
            Run("valid_full_checkpoint", delegate { var p = CreateCheckpoint(root, true, false); var r = new CheckpointValidator().Validate(p, null); Assert(r.Valid && r.DatabaseEligible && r.FullEligible && r.QdrantStructurallyValid, r.ErrorCode); });
            Run("missing_manifest", delegate { var p = Path.Combine(root, "missing"); Directory.CreateDirectory(p); var r = new CheckpointValidator().Validate(p, null); Assert(!r.Valid && r.ErrorCode == "backup_manifest_missing", r.ErrorCode); });
            Run("hash_mismatch", delegate { var p = CreateCheckpoint(root, false, false); File.AppendAllText(Path.Combine(p, "artifacts", "postgres.dump"), "x"); var r = new CheckpointValidator().Validate(p, null); Assert(!r.Valid && r.ErrorCode == "backup_artifact_size_mismatch", r.ErrorCode); });
            Run("traversal_rejected", delegate { var p = CreateCheckpoint(root, false, false); ReplaceArtifactPath(p, "../postgres.dump"); var r = new CheckpointValidator().Validate(p, null); Assert(!r.Valid && r.ErrorCode == "backup_artifact_path_invalid", r.ErrorCode); });
            Run("nul_qdrant_rejected", delegate { var p = CreateCheckpoint(root, true, true); var r = new CheckpointValidator().Validate(p, null); Assert(r.Valid && !r.FullEligible && !r.QdrantStructurallyValid && r.QdrantReason == "wal_first_index_empty_or_nul", r.QdrantReason); });
            Run("future_backup_rejected", delegate { var p = CreateCheckpoint(root, false, false); UpdateManifest(p, map => map["app_version"] = "9.0.0+1"); var r = new CheckpointValidator().Validate(p, null); Assert(r.Valid && !r.DatabaseEligible && r.Compatibility == CompatibilityKind.NewerUnsupported, r.CompatibilityLabel); });
            Run("relative_path_safety", delegate { Assert(CheckpointValidator.IsSafeRelativePath("artifacts/postgres.dump"), "valid rejected"); Assert(!CheckpointValidator.IsSafeRelativePath("../postgres.dump"), "traversal accepted"); Assert(!CheckpointValidator.IsSafeRelativePath("C:\\x"), "absolute accepted"); });
            Run("confirmation_exact", delegate { Assert(ConfirmationPolicy.IsSatisfied(RestoreMode.Database, true, "PRZYWRÓĆ"), "db token"); Assert(!ConfirmationPolicy.IsSatisfied(RestoreMode.Database, true, "przywróć"), "case accepted"); Assert(ConfirmationPolicy.IsSatisfied(RestoreMode.Full, true, "PRZYWRÓĆ SYSTEM"), "full token"); Assert(!ConfirmationPolicy.IsSatisfied(RestoreMode.Full, false, "PRZYWRÓĆ SYSTEM"), "ack bypass"); });
            Run("offline_without_backend_history", delegate { var p = CreateCheckpoint(root, false, false); Environment.SetEnvironmentVariable("DATABASE_URL", "postgresql://unavailable"); var r = new CheckpointValidator().Validate(p, null); Assert(r.Valid && r.DatabaseEligible, r.ErrorCode); Environment.SetEnvironmentVariable("DATABASE_URL", null); });
            Run("helper_integrity", delegate { var p = CreateHelperPackage(root); Assert(HelperIntegrity.Verify(p) == "1.0.0", "helper valid rejected"); File.AppendAllText(Path.Combine(p, "helpers", "restore-checkpoint.ps1"), "tamper"); bool rejected = false; try { HelperIntegrity.Verify(p); } catch (InvalidDataException e) { rejected = e.Message == "recovery_helper_size_mismatch" || e.Message == "recovery_helper_hash_mismatch"; } Assert(rejected, "helper tamper accepted"); });
        }
        finally { try { Directory.Delete(root, true); } catch { } }
        Console.WriteLine("RECOVERY_UNIT_TESTS=" + passed + "/" + (passed + failed) + " PASS");
        return failed == 0 ? 0 : 1;
    }

    public static string ValidateCheckpoint(string path)
    {
        var result = new CheckpointValidator().Validate(path, null);
        return new JavaScriptSerializer().Serialize(new Dictionary<string, object> {
            { "valid", result.Valid }, { "error_code", result.ErrorCode }, { "database_eligible", result.DatabaseEligible },
            { "full_eligible", result.FullEligible }, { "artifacts", result.ArtifactCount }, { "bytes", result.TotalBytes },
            { "qdrant_structural", result.QdrantStructurallyValid }, { "qdrant_restore_verified", result.QdrantRestoreVerified }
        });
    }

    public static string VerifyPackage(string path) { return HelperIntegrity.Verify(path); }

    private static void Run(string name, Action body)
    {
        try { body(); passed++; Console.WriteLine("PASS " + name); }
        catch (Exception error) { failed++; Console.WriteLine("FAIL " + name + ": " + error.Message); }
    }

    private static void Assert(bool condition, string detail) { if (!condition) throw new InvalidOperationException(detail); }

    private static string CreateCheckpoint(string root, bool full, bool nulIndex)
    {
        var path = Path.Combine(root, Guid.NewGuid().ToString("N")); var artifacts = Path.Combine(path, "artifacts"); Directory.CreateDirectory(artifacts);
        File.WriteAllBytes(Path.Combine(artifacts, "postgres.dump"), Encoding.ASCII.GetBytes("PGDMP\x01\x0f\x00test"));
        if (full)
        {
            foreach (var name in new[] { "document-storage.tar.gz", "release-stable.tar.gz", "n8n-workflows.json", "n8n-credentials.encrypted.json", "configuration.tar.gz" }) File.WriteAllText(Path.Combine(artifacts, name), name.EndsWith(".json") ? "[]" : "test");
            CreateQdrantSnapshot(path, Path.Combine(artifacts, "qdrant.snapshot"), nulIndex);
        }
        WriteManifest(path, full); return path;
    }

    private static void CreateQdrantSnapshot(string checkpoint, string target, bool nulIndex)
    {
        var source = Path.Combine(checkpoint, "qdrant-source"); Directory.CreateDirectory(Path.Combine(source, "0", "wal"));
        File.WriteAllText(Path.Combine(source, "config.json"), "{}"); File.WriteAllText(Path.Combine(source, "version.info"), "1.18.3"); File.WriteAllText(Path.Combine(source, "0", "shard_config.json"), "{}");
        File.WriteAllBytes(Path.Combine(source, "0", "wal", "first-index"), nulIndex ? new byte[15] : Encoding.UTF8.GetBytes("{\"ack_index\":5}"));
        using (var p = Process.Start(new ProcessStartInfo("tar.exe", "-cf \"" + target + "\" -C \"" + source + "\" config.json version.info 0/shard_config.json 0/wal/first-index") { UseShellExecute = false, CreateNoWindow = true })) { p.WaitForExit(); Assert(p.ExitCode == 0, "tar create"); }
        Directory.Delete(source, true);
    }

    private static void WriteManifest(string path, bool full)
    {
        var list = new List<object>();
        foreach (var file in Directory.GetFiles(Path.Combine(path, "artifacts")))
        {
            var info = new FileInfo(file); list.Add(new Dictionary<string, object> { { "file", "artifacts/" + info.Name }, { "bytes", info.Length }, { "sha256", CheckpointValidator.HashFile(file) } });
        }
        var root = new Dictionary<string, object> {
            { "schema_version", "NEXT_STABIL_BACKUP_V1" }, { "scope", full ? "full" : "database" }, { "app_version", "1.0.2+25" },
            { "created_at", "2026-08-21T00:00:00Z" }, { "source_head", "test" }, { "db_revision", CheckpointValidator.CurrentDbRevision },
            { "qdrant_restore_verified", full },
            { "qdrant_restore_result", full ? (object)new Dictionary<string, object> { { "verified", true }, { "points", 2 }, { "dimensions", 1024 }, { "distance", "Cosine" }, { "production_volume_mounted", false } } : null },
            { "secrets_in_protected_backup", false }, { "artifacts", list }
        };
        File.WriteAllText(Path.Combine(path, "backup-manifest.json"), new JavaScriptSerializer().Serialize(root), Encoding.UTF8);
    }

    private static void ReplaceArtifactPath(string path, string replacement)
    {
        UpdateManifest(path, map => { var artifacts = (object[])map["artifacts"]; ((IDictionary<string, object>)artifacts[0])["file"] = replacement; });
    }

    private static void UpdateManifest(string path, Action<IDictionary<string, object>> change)
    {
        var file = Path.Combine(path, "backup-manifest.json"); var serializer = new JavaScriptSerializer(); var root = (IDictionary<string, object>)serializer.DeserializeObject(File.ReadAllText(file)); change(root); File.WriteAllText(file, serializer.Serialize(root), Encoding.UTF8);
    }

    private static string CreateHelperPackage(string root)
    {
        var package = Path.Combine(root, "helper-" + Guid.NewGuid().ToString("N")); var helpers = Path.Combine(package, "helpers"); Directory.CreateDirectory(helpers);
        var helper = Path.Combine(helpers, "restore-checkpoint.ps1"); File.WriteAllText(helper, "throw 'test'"); var info = new FileInfo(helper);
        var manifest = new Dictionary<string, object> { { "schema", "NEXT_STABIL_RECOVERY_TOOL_V1" }, { "tool_version", "1.0.0" }, { "helpers", new object[] { new Dictionary<string, object> { { "file", "helpers/restore-checkpoint.ps1" }, { "bytes", info.Length }, { "sha256", CheckpointValidator.HashFile(helper) } } } } };
        File.WriteAllText(Path.Combine(package, "recovery-tool-manifest.json"), new JavaScriptSerializer().Serialize(manifest), Encoding.UTF8); return package;
    }
}
