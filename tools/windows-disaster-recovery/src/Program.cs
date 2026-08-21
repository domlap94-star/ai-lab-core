using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using System.Runtime.InteropServices;

namespace NextStabil.Recovery
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                if (args.Length >= 2 && args[0] == "--validate") return ValidateCli(args[1], Array.IndexOf(args, "--json") >= 0);
                if (args.Length >= 2 && args[0] == "--proof") return ProofCli(args);
                var initialPath = args.Length >= 2 && args[0] == "--open" ? args[1] : null;
                HelperIntegrity.Verify(AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\'));
                Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new MainForm(initialPath)); return 0;
            }
            catch (Exception error)
            {
                if (Environment.UserInteractive) MessageBox.Show("Recovery App nie może wystartować:\r\n" + error.Message, "NEXT Stabil — Recovery", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 2;
            }
        }

        private static int ValidateCli(string path, bool json)
        {
            AttachConsoleOutput();
            var result = new CheckpointValidator().Validate(path, null);
            if (json)
            {
                var payload = new Dictionary<string, object>
                {
                    { "valid", result.Valid }, { "error_code", result.ErrorCode }, { "checkpoint", result.CheckpointPath },
                    { "manifest_sha256", result.ManifestSha256 }, { "compatibility", result.CompatibilityLabel },
                    { "database_eligible", result.DatabaseEligible }, { "full_eligible", result.FullEligible },
                    { "qdrant_snapshot_structurally_valid", result.QdrantStructurallyValid },
                    { "qdrant_restore_verified", result.QdrantRestoreVerified }, { "artifact_count", result.ArtifactCount },
                    { "total_bytes", result.TotalBytes }, { "secret_escrow_required", result.SecretEscrowRequired }
                };
                Console.OutputEncoding = Encoding.UTF8; Console.WriteLine(new JavaScriptSerializer().Serialize(payload));
            }
            else Console.WriteLine(result.Valid ? "CHECKPOINT_VALID=YES" : "CHECKPOINT_VALID=NO\r\nERROR=" + result.ErrorCode);
            return result.Valid ? 0 : 1;
        }

        private static int ProofCli(string[] args)
        {
            AttachConsoleOutput();
            var path = args[1]; var mode = Array.IndexOf(args, "--full") >= 0 ? RestoreMode.Full : RestoreMode.Database;
            HelperIntegrity.Verify(AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\'));
            var checkpoint = new CheckpointValidator().Validate(path, null);
            if (!checkpoint.Valid || (mode == RestoreMode.Full ? !checkpoint.FullEligible : !checkpoint.DatabaseEligible)) return 1;
            var result = new RecoveryEngine(AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\')).ExecuteProof(checkpoint, mode, Console.WriteLine);
            return result.ExitCode;
        }

        private static void AttachConsoleOutput()
        {
            if (AttachConsole(-1))
            {
                var writer = new StreamWriter(Console.OpenStandardOutput()) { AutoFlush = true };
                Console.SetOut(writer);
            }
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AttachConsole(int processId);
    }
}
