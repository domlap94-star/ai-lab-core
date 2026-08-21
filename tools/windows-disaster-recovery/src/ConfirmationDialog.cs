using System;
using System.Drawing;
using System.Windows.Forms;

namespace NextStabil.Recovery
{
    internal sealed class ConfirmationDialog : Form
    {
        private readonly CheckBox acknowledge;
        private readonly TextBox token;
        private readonly Button confirm;
        private readonly string requiredToken;

        public bool Confirmed { get; private set; }

        public ConfirmationDialog(RestoreMode mode, string checkpoint)
        {
            requiredToken = ConfirmationPolicy.RequiredToken(mode);
            Text = "Potwierdzenie przywracania";
            Width = 620; Height = 440; StartPosition = FormStartPosition.CenterParent;
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false;
            var panel = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(22), RowCount = 8, ColumnCount = 1, AutoScroll = true };
            panel.RowStyles.Clear();
            var title = new Label { Text = mode == RestoreMode.Full ? "PRZYWRÓCENIE PEŁNEGO SYSTEMU" : "PRZYWRACANIE BAZY DANYCH", AutoSize = true, Font = new Font(SystemFonts.MessageBoxFont, FontStyle.Bold) };
            var source = new Label { Text = "ŹRÓDŁO:\r\n" + checkpoint, AutoSize = true, MaximumSize = new Size(550, 0) };
            var warning = new Label { Text = mode == RestoreMode.Full ? "Baza danych, Dokumenty, Qdrant oraz n8n/konfiguracja zostaną przywrócone. Usługi NEXT Stabil zostaną czasowo zatrzymane." : "Bieżąca baza danych zostanie zastąpiona. Przed operacją aplikacja spróbuje utworzyć pełny backup bezpieczeństwa.", AutoSize = true, MaximumSize = new Size(550, 0) };
            acknowledge = new CheckBox { Text = "Rozumiem, że aktualne dane mogą zostać zastąpione.", AutoSize = true };
            token = new TextBox { Width = 260 };
            confirm = new Button { Text = "Przywróć", AutoSize = true, Enabled = false };
            var cancel = new Button { Text = "Anuluj", AutoSize = true, DialogResult = DialogResult.Cancel };
            var buttons = new FlowLayoutPanel { AutoSize = true, FlowDirection = FlowDirection.RightToLeft, Dock = DockStyle.Fill };
            buttons.Controls.Add(confirm); buttons.Controls.Add(cancel);
            panel.Controls.Add(title); panel.Controls.Add(source); panel.Controls.Add(warning); panel.Controls.Add(acknowledge);
            panel.Controls.Add(new Label { Text = "Wpisz dokładnie: " + requiredToken, AutoSize = true }); panel.Controls.Add(token); panel.Controls.Add(buttons);
            Controls.Add(panel);
            acknowledge.CheckedChanged += delegate { RefreshButton(); };
            token.TextChanged += delegate { RefreshButton(); };
            confirm.Click += delegate { Confirmed = true; DialogResult = DialogResult.OK; Close(); };
            AcceptButton = confirm; CancelButton = cancel;
        }

        private void RefreshButton() { confirm.Enabled = ConfirmationPolicy.IsSatisfied(requiredToken == "PRZYWRÓĆ SYSTEM" ? RestoreMode.Full : RestoreMode.Database, acknowledge.Checked, token.Text); }
    }
}
