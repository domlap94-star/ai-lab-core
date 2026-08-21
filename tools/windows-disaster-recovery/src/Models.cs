using System;
using System.Collections.Generic;

namespace NextStabil.Recovery
{
    internal enum RestoreMode { Database, Full }

    internal enum CompatibilityKind
    {
        Compatible,
        OlderSupported,
        RequiresMigration,
        NewerUnsupported,
        Invalid
    }

    internal sealed class ArtifactInfo
    {
        public string RelativePath { get; set; }
        public string FullPath { get; set; }
        public long Bytes { get; set; }
        public string Sha256 { get; set; }
    }

    internal sealed class CheckpointResult
    {
        public string CheckpointPath { get; set; }
        public string ManifestPath { get; set; }
        public string ManifestSha256 { get; set; }
        public bool Valid { get; set; }
        public string ErrorCode { get; set; }
        public string CreatedAt { get; set; }
        public string Scope { get; set; }
        public string AppVersion { get; set; }
        public string SourceHead { get; set; }
        public string DbRevision { get; set; }
        public long TotalBytes { get; set; }
        public int ArtifactCount { get; set; }
        public CompatibilityKind Compatibility { get; set; }
        public bool DatabaseAvailable { get; set; }
        public bool DocumentsAvailable { get; set; }
        public bool QdrantAvailable { get; set; }
        public bool N8nConfigAvailable { get; set; }
        public bool ReleaseConfigAvailable { get; set; }
        public bool DatabaseArchiveReadable { get; set; }
        public bool QdrantStructurallyValid { get; set; }
        public bool QdrantRestoreVerified { get; set; }
        public long QdrantPoints { get; set; }
        public int QdrantDimensions { get; set; }
        public string QdrantDistance { get; set; }
        public string QdrantReason { get; set; }
        public bool DatabaseEligible { get; set; }
        public bool FullEligible { get; set; }
        public bool SecretEscrowRequired { get; set; }
        public Dictionary<string, ArtifactInfo> Artifacts { get; private set; }
        public List<string> Stages { get; private set; }

        public CheckpointResult()
        {
            Artifacts = new Dictionary<string, ArtifactInfo>(StringComparer.OrdinalIgnoreCase);
            Stages = new List<string>();
            Compatibility = CompatibilityKind.Invalid;
            QdrantDistance = string.Empty;
        }

        public string CompatibilityLabel
        {
            get
            {
                switch (Compatibility)
                {
                    case CompatibilityKind.Compatible: return "ZGODNY";
                    case CompatibilityKind.OlderSupported: return "STARSZY, OBSŁUGIWANY";
                    case CompatibilityKind.RequiresMigration: return "WYMAGA MIGRACJI PO ODTWORZENIU";
                    case CompatibilityKind.NewerUnsupported: return "NIEOBSŁUGIWANY — nowszy backup";
                    default: return "NIEPRAWIDŁOWY";
                }
            }
        }
    }

    internal sealed class ValidationProgress
    {
        public string Stage { get; set; }
        public string Detail { get; set; }
    }

    internal sealed class RecoveryExecutionResult
    {
        public string OperationId { get; set; }
        public string FinalStatus { get; set; }
        public string ReportPath { get; set; }
        public string ErrorCode { get; set; }
        public int ExitCode { get; set; }
    }
}
