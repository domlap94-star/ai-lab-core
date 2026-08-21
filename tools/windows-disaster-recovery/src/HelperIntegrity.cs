using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;

namespace NextStabil.Recovery
{
    internal sealed class HelperIntegrity
    {
        public static string Verify(string applicationDirectory)
        {
            var manifestPath = Path.Combine(applicationDirectory, "recovery-tool-manifest.json");
            if (!File.Exists(manifestPath)) throw new InvalidDataException("recovery_helper_manifest_missing");
            var json = File.ReadAllText(manifestPath, Encoding.UTF8).TrimStart('\uFEFF');
            var root = new JavaScriptSerializer().DeserializeObject(json) as IDictionary<string, object>;
            if (root == null || Convert.ToString(Value(root, "schema"), CultureInfo.InvariantCulture) != "NEXT_STABIL_RECOVERY_TOOL_V1")
                throw new InvalidDataException("recovery_helper_manifest_invalid");
            var helpers = Value(root, "helpers") as object[];
            if (helpers == null || helpers.Length == 0) throw new InvalidDataException("recovery_helpers_missing");
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var raw in helpers)
            {
                var item = raw as IDictionary<string, object>;
                if (item == null) throw new InvalidDataException("recovery_helper_record_invalid");
                var relative = Convert.ToString(Value(item, "file"), CultureInfo.InvariantCulture);
                if (!CheckpointValidator.IsSafeRelativePath(relative) || !seen.Add(relative))
                    throw new InvalidDataException("recovery_helper_path_invalid");
                var full = Path.GetFullPath(Path.Combine(applicationDirectory, relative.Replace('/', Path.DirectorySeparatorChar)));
                var prefix = applicationDirectory.TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
                if (!full.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) || !File.Exists(full))
                    throw new InvalidDataException("recovery_helper_missing");
                long expectedBytes;
                if (!long.TryParse(Convert.ToString(Value(item, "bytes"), CultureInfo.InvariantCulture), out expectedBytes) || expectedBytes < 1)
                    throw new InvalidDataException("recovery_helper_size_invalid");
                if (new FileInfo(full).Length != expectedBytes) throw new InvalidDataException("recovery_helper_size_mismatch");
                var expectedHash = Convert.ToString(Value(item, "sha256"), CultureInfo.InvariantCulture);
                if (!string.Equals(CheckpointValidator.HashFile(full), expectedHash, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("recovery_helper_hash_mismatch");
            }
            return Convert.ToString(Value(root, "tool_version"), CultureInfo.InvariantCulture) ?? "1.0.0";
        }

        private static object Value(IDictionary<string, object> map, string key)
        { object value; return map.TryGetValue(key, out value) ? value : null; }
    }
}
