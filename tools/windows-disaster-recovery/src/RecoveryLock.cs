using System;
using System.IO;
using System.Threading;

namespace NextStabil.Recovery
{
    internal sealed class RecoveryLock : IDisposable
    {
        private readonly Mutex mutex;
        private readonly string lockPath;
        private bool held;

        public RecoveryLock()
        {
            mutex = new Mutex(false, @"Global\NEXT_STABIL_RECOVERY_OPERATION_V1");
            var root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "NEXT Stabil Recovery");
            Directory.CreateDirectory(root);
            lockPath = Path.Combine(root, "recovery-operation.lock");
        }

        public void Acquire(string operationId)
        {
            try { held = mutex.WaitOne(0, false); }
            catch (AbandonedMutexException) { held = true; }
            if (!held) throw new InvalidOperationException("recovery_operation_already_running");
            File.WriteAllText(lockPath, operationId + "|" + DateTime.UtcNow.ToString("o"));
        }

        public void Dispose()
        {
            try { if (File.Exists(lockPath)) File.Delete(lockPath); } catch { }
            if (held) { mutex.ReleaseMutex(); held = false; }
            mutex.Dispose();
        }
    }
}
