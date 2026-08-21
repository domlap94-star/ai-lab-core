using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Text;
using System.Windows.Forms;

namespace NextStabil.Recovery
{
    internal sealed class MainForm : Form
    {
        private readonly CheckpointValidator validator = new CheckpointValidator();
        private readonly RecoveryEngine engine;
        private readonly TextBox checkpointPath;
        private readonly Label status;
        private readonly Label details;
        private readonly Label systemState;
        private readonly ProgressBar progress;
        private readonly Button validateButton;
        private readonly Button databaseButton;
        private readonly Button fullButton;
        private readonly Button reportButton;
        private CheckpointResult checkpoint;
        private string lastReport;

        public MainForm(string initialPath)
        {
            engine = new RecoveryEngine(AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\'));
            Text = "NEXT Stabil — Recovery";
            MinimumSize = new Size(720, 650); Size = new Size(860, 760); StartPosition = FormStartPosition.CenterScreen;
            Font = SystemFonts.MessageBoxFont;

            var root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(24), ColumnCount = 1, RowCount = 11, AutoScroll = true };
            root.RowStyles.Clear();
            root.Controls.Add(new Label { Text = "NEXT Stabil — Recovery", AutoSize = true, Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 18, FontStyle.Bold) });
            root.Controls.Add(new Label { Text = "Recovery Tool 1.0.0 · działa bez Fluttera, backendu, JWT i historii PostgreSQL", AutoSize = true, ForeColor = Color.DimGray });

            var picker = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2, Margin = new Padding(0, 18, 0, 8) };
            picker.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); picker.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            checkpointPath = new TextBox { Dock = DockStyle.Fill, ReadOnly = true, Text = initialPath ?? string.Empty };
            var pickButton = new Button { Text = "Wybierz folder backupu", AutoSize = true, Margin = new Padding(8, 0, 0, 0) };
            pickButton.Click += PickFolder;
            picker.Controls.Add(checkpointPath, 0, 0); picker.Controls.Add(pickButton, 1, 0); root.Controls.Add(picker);

            validateButton = new Button { Text = "Sprawdź backup", AutoSize = true, Enabled = !string.IsNullOrWhiteSpace(initialPath) };
            validateButton.Click += delegate { BeginValidation(); };
            root.Controls.Add(validateButton);
            progress = new ProgressBar { Dock = DockStyle.Top, Height = 8, Style = ProgressBarStyle.Marquee, Visible = false, MarqueeAnimationSpeed = 30 };
            root.Controls.Add(progress);
            status = new Label { Text = "Wybierz folder zawierający backup-manifest.json.", AutoSize = true, MaximumSize = new Size(780, 0), Margin = new Padding(0, 12, 0, 8) };
            root.Controls.Add(status);
            details = new Label { Text = "", AutoSize = true, MaximumSize = new Size(780, 0), BorderStyle = BorderStyle.FixedSingle, Padding = new Padding(12), Visible = false };
            root.Controls.Add(details);

            var operations = new GroupBox { Text = "Dostępne operacje", Dock = DockStyle.Top, AutoSize = true, Padding = new Padding(14), Margin = new Padding(0, 16, 0, 0) };
            var operationButtons = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };
            databaseButton = new Button { Text = "Przywróć bazę danych", AutoSize = true, Enabled = false };
            fullButton = new Button { Text = "Przywróć cały system", AutoSize = true, Enabled = false };
            reportButton = new Button { Text = "Pokaż raport", AutoSize = true, Enabled = false };
            databaseButton.Click += delegate { BeginRestore(RestoreMode.Database); };
            fullButton.Click += delegate { BeginRestore(RestoreMode.Full); };
            reportButton.Click += ShowReport;
            operationButtons.Controls.Add(databaseButton); operationButtons.Controls.Add(fullButton); operationButtons.Controls.Add(reportButton);
            operations.Controls.Add(operationButtons); root.Controls.Add(operations);

            systemState = new Label { Text = "Stan środowiska: sprawdzanie…", AutoSize = true, MaximumSize = new Size(780, 0), Margin = new Padding(0, 18, 0, 0), ForeColor = Color.DimGray };
            root.Controls.Add(systemState);
            root.Controls.Add(new Label { Text = "Sekrety środowiskowe nie są częścią checkpointu. Przy odtwarzaniu nowego hosta wymagany jest zewnętrzny sejf/escrow.", AutoSize = true, MaximumSize = new Size(780, 0), ForeColor = Color.DarkOrange, Margin = new Padding(0, 14, 0, 0) });
            Controls.Add(root);
            Shown += delegate
            {
                lastReport = FindLatestReport();
                reportButton.Enabled = !string.IsNullOrWhiteSpace(lastReport);
                ProbeEnvironment();
                if (!string.IsNullOrWhiteSpace(initialPath)) BeginValidation();
            };
        }

        private void PickFolder(object sender, EventArgs args)
        {
            using (var dialog = new FolderBrowserDialog { Description = "Wybierz folder checkpointu NEXT Stabil", ShowNewFolderButton = false })
            {
                if (dialog.ShowDialog(this) != DialogResult.OK) return;
                checkpointPath.Text = dialog.SelectedPath; validateButton.Enabled = true; ResetValidation(); BeginValidation();
            }
        }

        private void ResetValidation()
        {
            checkpoint = null; databaseButton.Enabled = false; fullButton.Enabled = false; details.Visible = false;
            status.Text = "Checkpoint nie został jeszcze zweryfikowany.";
        }

        private void BeginValidation()
        {
            if (string.IsNullOrWhiteSpace(checkpointPath.Text)) return;
            SetBusy(true); status.Text = "Odczyt manifestu…";
            var worker = new BackgroundWorker { WorkerReportsProgress = true };
            worker.DoWork += delegate(object sender, DoWorkEventArgs e)
            {
                e.Result = validator.Validate(checkpointPath.Text, p => ((BackgroundWorker)sender).ReportProgress(0, p));
            };
            worker.ProgressChanged += delegate(object sender, ProgressChangedEventArgs e)
            {
                var item = e.UserState as ValidationProgress; if (item != null) status.Text = item.Stage + "\r\n" + item.Detail;
            };
            worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs e)
            {
                SetBusy(false);
                if (e.Error != null) { status.Text = "✗ Walidacja nie powiodła się: " + e.Error.Message; return; }
                checkpoint = (CheckpointResult)e.Result; RenderCheckpoint();
            };
            worker.RunWorkerAsync();
        }

        private void RenderCheckpoint()
        {
            if (checkpoint == null || !checkpoint.Valid)
            {
                status.Text = "✗ Backup nieprawidłowy: " + (checkpoint == null ? "checkpoint_validation_failed" : checkpoint.ErrorCode);
                details.Visible = false; databaseButton.Enabled = false; fullButton.Enabled = false; return;
            }
            status.Text = "✓ Manifest znaleziony\r\n✓ Integralność zweryfikowana\r\n✓ Klasyfikacja zgodności zakończona";
            details.Text = string.Join("\r\n", new[] {
                "Wybrany checkpoint: " + checkpoint.CheckpointPath,
                "Data: " + checkpoint.CreatedAt,
                "Wersja NEXT Stabil: " + checkpoint.AppVersion,
                "Rewizja bazy: " + checkpoint.DbRevision,
                "Zakres: " + checkpoint.Scope,
                "Rozmiar: " + FormatBytes(checkpoint.TotalBytes) + " · artefakty: " + checkpoint.ArtifactCount,
                "Zgodność: " + checkpoint.CompatibilityLabel,
                "Baza danych: " + YesNo(checkpoint.DatabaseAvailable),
                "Dokumenty: " + YesNo(checkpoint.DocumentsAvailable),
                "Qdrant: " + YesNo(checkpoint.QdrantAvailable) + " · struktura: " + YesNo(checkpoint.QdrantStructurallyValid) + " · drill: " + YesNo(checkpoint.QdrantRestoreVerified),
                "n8n/konfiguracja: " + YesNo(checkpoint.N8nConfigAvailable && checkpoint.ReleaseConfigAvailable),
                "Sekrety środowiskowe: wymagane z zewnętrznego sejfu/escrow"
            });
            details.Visible = true; databaseButton.Enabled = checkpoint.DatabaseEligible; fullButton.Enabled = checkpoint.FullEligible;
            if (!checkpoint.FullEligible && checkpoint.QdrantAvailable && !checkpoint.QdrantStructurallyValid)
                status.Text += "\r\nPełne przywracanie niedostępne: qdrant_snapshot_invalid (" + checkpoint.QdrantReason + ")";
        }

        private void BeginRestore(RestoreMode mode)
        {
            if (checkpoint == null || !checkpoint.Valid) return;
            if (!RecoveryEngine.IsAdministrator())
            {
                if (MessageBox.Show(this, "Przywracanie wymaga uprawnień Administratora. Uruchomić ponownie z UAC?", "Wymagane uprawnienia", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes)
                { RecoveryEngine.RelaunchElevated(new[] { "--open", checkpoint.CheckpointPath }); Close(); }
                return;
            }
            using (var dialog = new ConfirmationDialog(mode, checkpoint.CheckpointPath))
            {
                if (dialog.ShowDialog(this) != DialogResult.OK || !dialog.Confirmed) { status.Text = "CANCELLED BEFORE CUTOVER"; return; }
            }
            MessageBox.Show(this, "Produkcja pozostaje zabezpieczona bramą FOLLOWUP_PRODUCTION_RESTORE_APPROVAL_REQUIRED. Ten build zawiera kompletne proof/staging, ale nie zawiera modułu live cutover. Nie wykonano żadnej zmiany.", "Brama operacyjna", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            status.Text = "CANCELLED BEFORE CUTOVER — production_restore_approval_required";
        }

        private void ProbeEnvironment()
        {
            var worker = new BackgroundWorker();
            worker.DoWork += delegate(object sender, DoWorkEventArgs e)
            {
                var docker = CommandOk("docker.exe", "version --format {{.Server.Version}}", 10000);
                var backend = HttpOk("http://127.0.0.1:8000/health");
                var qdrant = HttpOk("http://127.0.0.1:6333/");
                e.Result = "Stan środowiska: Docker " + YesNo(docker) + " · backend " + YesNo(backend) + " · Qdrant " + YesNo(qdrant) + ". Niedostępny backend/PostgreSQL nie blokuje wyboru i walidacji checkpointu.";
            };
            worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs e) { systemState.Text = e.Error == null ? Convert.ToString(e.Result) : "Stan środowiska: częściowo niedostępny"; };
            worker.RunWorkerAsync();
        }

        private void ShowReport(object sender, EventArgs args)
        {
            if (!string.IsNullOrWhiteSpace(lastReport) && File.Exists(lastReport)) Process.Start(new ProcessStartInfo(lastReport) { UseShellExecute = true });
        }

        private void SetBusy(bool busy) { progress.Visible = busy; validateButton.Enabled = !busy && !string.IsNullOrWhiteSpace(checkpointPath.Text); databaseButton.Enabled = !busy && checkpoint != null && checkpoint.DatabaseEligible; fullButton.Enabled = !busy && checkpoint != null && checkpoint.FullEligible; }
        private static bool HttpOk(string url) { try { var request = (HttpWebRequest)WebRequest.Create(url); request.Timeout = 1500; request.Method = "GET"; using (var response = (HttpWebResponse)request.GetResponse()) return (int)response.StatusCode < 500; } catch { return false; } }
        private static bool CommandOk(string file, string arguments, int timeout) { try { using (var process = Process.Start(new ProcessStartInfo(file, arguments) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true })) { if (!process.WaitForExit(timeout)) { process.Kill(); return false; } return process.ExitCode == 0; } } catch { return false; } }
        private static string YesNo(bool value) { return value ? "TAK" : "NIE"; }
        private static string FormatBytes(long bytes) { string[] units = { "B", "KiB", "MiB", "GiB", "TiB" }; double value = bytes; var index = 0; while (value >= 1024 && index < units.Length - 1) { value /= 1024; index++; } return value.ToString(index == 0 ? "0" : "0.##") + " " + units[index]; }
        private static string FindLatestReport()
        {
            try
            {
                var root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "NEXT Stabil Recovery");
                if (!Directory.Exists(root)) return null;
                var files = new DirectoryInfo(root).GetFiles("NEXT-STABIL-RECOVERY-*.json");
                Array.Sort(files, delegate(FileInfo a, FileInfo b) { return b.LastWriteTimeUtc.CompareTo(a.LastWriteTimeUtc); });
                return files.Length == 0 ? null : files[0].FullName;
            }
            catch { return null; }
        }
    }
}
