using System;

namespace NextStabil.Recovery
{
    internal static class ConfirmationPolicy
    {
        public static string RequiredToken(RestoreMode mode) { return mode == RestoreMode.Full ? "PRZYWRÓĆ SYSTEM" : "PRZYWRÓĆ"; }
        public static bool IsSatisfied(RestoreMode mode, bool acknowledged, string typed)
        { return acknowledged && string.Equals(typed, RequiredToken(mode), StringComparison.Ordinal); }
    }
}
