using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Principal;
using System.Text;
using System.Web.Script.Serialization;

namespace NextStabil.Recovery
{
    internal sealed class RecoveryEngine
    {
        private readonly string applicationDirectory;

        public RecoveryEngine(string applicationDirectory) { this.applicationDirectory = applicationDirectory; }

        public static bool IsAdministrator()
        {
            using (var identity = WindowsIdentity.GetCurrent())
                return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
        }

        public static void RelaunchElevated(string[] arguments)
        {
            var info = new ProcessStartInfo
            {
                FileName = System.Reflection.Assembly.GetExecutingAssembly().Location,
                Arguments = JoinArguments(arguments),
                UseShellExecute = true,
                Verb = "runas"
            };
            Process.Start(info);
        }

        public RecoveryExecutionResult Execute(CheckpointResult checkpoint, RestoreMode mode, bool allowSafetyOverride, Action<string> output)
        {
            HelperIntegrity.Verify(applicationDirectory);
            var operationId = Guid.NewGuid().ToString("N");
            using (var operationLock = new RecoveryLock())
            {
                operationLock.Acquire(operationId);
                var script = Path.Combine(applicationDirectory, "helpers", "restore-checkpoint.ps1");
                var arguments = new StringBuilder();
                arguments.Append("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ").Append(Quote(script));
                arguments.Append(" -CheckpointPath ").Append(Quote(checkpoint.CheckpointPath));
                arguments.Append(" -Mode ").Append(mode == RestoreMode.Full ? "Full" : "Database");
                arguments.Append(" -OperationId ").Append(operationId);
                if (allowSafetyOverride) arguments.Append(" -ContinueWithoutSafetyBackup -SafetyOverrideToken ").Append(Quote("KONTYNUUJ BEZ BACKUPU"));

                var info = new ProcessStartInfo("powershell.exe", arguments.ToString())
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    WorkingDirectory = applicationDirectory
                };
                using (var process = Process.Start(info))
                {
                    var stdout = new StringBuilder();
                    process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) { stdout.AppendLine(e.Data); if (output != null) output(e.Data); } };
                    process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null && output != null) output(e.Data); };
                    process.BeginOutputReadLine(); process.BeginErrorReadLine(); process.WaitForExit();
                    var report = ParseResult(stdout.ToString());
                    report.OperationId = operationId;
                    report.ExitCode = process.ExitCode;
                    if (string.IsNullOrEmpty(report.FinalStatus)) report.FinalStatus = process.ExitCode == 0 ? "PASS" : "FAILED";
                    return report;
                }
            }
        }

        public RecoveryExecutionResult ExecuteProof(CheckpointResult checkpoint, RestoreMode mode, Action<string> output)
        {
            HelperIntegrity.Verify(applicationDirectory);
            var operationId = Guid.NewGuid().ToString("N");
            using (var operationLock = new RecoveryLock())
            {
                operationLock.Acquire(operationId);
                var script = Path.Combine(applicationDirectory, "helpers", "restore-checkpoint.ps1");
                var args = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File " + Quote(script) +
                    " -CheckpointPath " + Quote(checkpoint.CheckpointPath) + " -Mode " + (mode == RestoreMode.Full ? "Full" : "Database") +
                    " -ProofOnly -OperationId " + operationId;
                var info = new ProcessStartInfo("powershell.exe", args) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true, WorkingDirectory = applicationDirectory };
                using (var process = Process.Start(info))
                {
                    var stdout = new StringBuilder();
                    process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) { stdout.AppendLine(e.Data); if (output != null) output(e.Data); } };
                    process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null && output != null) output(e.Data); };
                    process.BeginOutputReadLine(); process.BeginErrorReadLine(); process.WaitForExit();
                    var result = ParseResult(stdout.ToString()); result.OperationId = operationId; result.ExitCode = process.ExitCode;
                    if (string.IsNullOrEmpty(result.FinalStatus)) result.FinalStatus = process.ExitCode == 0 ? "PASS" : "FAILED";
                    return result;
                }
            }
        }

        private static RecoveryExecutionResult ParseResult(string text)
        {
            var result = new RecoveryExecutionResult();
            foreach (var line in text.Split(new[] { "\r\n", "\n" }, StringSplitOptions.RemoveEmptyEntries))
            {
                var index = line.IndexOf('='); if (index < 1) continue;
                var key = line.Substring(0, index); var value = line.Substring(index + 1);
                if (key == "RECOVERY_FINAL_STATUS") result.FinalStatus = value;
                else if (key == "RECOVERY_REPORT") result.ReportPath = value;
                else if (key == "RECOVERY_ERROR") result.ErrorCode = value;
            }
            return result;
        }

        private static string Quote(string value) { return "\"" + value.Replace("\"", "\\\"") + "\""; }
        private static string JoinArguments(IEnumerable<string> values) { var list = new List<string>(); foreach (var value in values) list.Add(Quote(value)); return string.Join(" ", list.ToArray()); }
    }
}
