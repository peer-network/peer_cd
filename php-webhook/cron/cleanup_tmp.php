<?php
declare(strict_types=1);

/**
 * Upload-post TMP cleanup
 * - Removes files older than 24h from runtime-data/media/tmp
 * - Logs per-run + summary
 * - Lock-file to avoid concurrent runs
 */

date_default_timezone_set('UTC');

// --- Paths ---
$projectRoot     = dirname(__DIR__);
$tmpDir          = $projectRoot . '/runtime-data/media/tmp';
$logRootDir      = $projectRoot . '/runtime-data/logs';
$workerLogDir    = $logRootDir . '/cron-workers/upload-post-tmp-files-cleanup';
$dailyLogPath    = $workerLogDir . '/' . date('Y-m-d') . '-upload-post-tmp-files-cleanup.log';
$summaryLogPath  = $logRootDir . '/cleanup.log';
$locksDir        = $projectRoot . '/runtime-data/locks';
$lockFilePath    = $locksDir . '/cleanup-upload-post-tmp.lock';

@mkdir($logRootDir, 0777, true);
@mkdir($workerLogDir, 0777, true);
@mkdir($locksDir, 0777, true);

function logLine(string $line): void {
    global $dailyLogPath;
    $ts  = date('Y-m-d H:i:s');
    $msg = "[$ts] $line\n";
    file_put_contents($dailyLogPath, $msg, FILE_APPEND);
    echo $msg;
}
function logSummary(string $line): void {
    global $summaryLogPath;
    $ts = date('Y-m-d H:i:s');
    file_put_contents($summaryLogPath, "[$ts] $line\n", FILE_APPEND);
}

if (!is_dir($tmpDir)) {
    logLine("WARN: tmp directory not found: {$tmpDir} (nothing to do)");
    logSummary("upload-post tmp cleanup: skipped (no tmp dir)");
    exit(0);
}

$lockFp = fopen($lockFilePath, 'c');
if ($lockFp === false || !flock($lockFp, LOCK_EX | LOCK_NB)) {
    logLine("INFO: another cleanup run is in progress; exiting");
    logSummary("upload-post tmp cleanup: skipped (lock held)");
    if (is_resource($lockFp)) fclose($lockFp);
    exit(0);
}

$now = time();
$ageThreshold = 24 * 3600;
$scanned=0; $deleted=0; $skipped=0; $errors=0; $freed=0; $dirsRemoved=0;

$tmpReal = realpath($tmpDir);
if ($tmpReal === false) {
    logLine("ERROR: realpath failed for {$tmpDir}");
    logSummary("upload-post tmp cleanup: failed (realpath)");
    flock($lockFp, LOCK_UN); fclose($lockFp); exit(1);
}
$prefix = rtrim($tmpReal, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;

$it = new RecursiveIteratorIterator(
    new RecursiveDirectoryIterator($tmpDir, FilesystemIterator::SKIP_DOTS|FilesystemIterator::CURRENT_AS_FILEINFO),
    RecursiveIteratorIterator::CHILD_FIRST
);

foreach ($it as $fi) {
    /** @var SplFileInfo $fi */
    $path = $fi->getPathname();
    if (!str_starts_with($path, $prefix)) { $skipped++; continue; }
    if ($fi->isLink()) { $skipped++; continue; }

    if ($fi->isFile()) {
        $scanned++;
        $base = $fi->getBasename();
        if ($base === '.gitkeep' || $base === '.gitignore') { $skipped++; continue; }
        $age = $now - $fi->getMTime();
        if ($age >= $ageThreshold) {
            $size = (int)$fi->getSize();
            if (@unlink($path)) {
                $deleted++; $freed += $size;
                logLine("DELETE file: {$path} (age=" . round($age/3600,1) . "h, bytes={$size})");
            } else { $errors++; logLine("ERROR: unlink failed: {$path}"); }
        } else { $skipped++; }
    } elseif ($fi->isDir()) {
        if (@rmdir($path)) { $dirsRemoved++; logLine("REMOVE empty dir: {$path}"); }
    }
}

$summary = sprintf(
    'upload-post tmp cleanup: scanned=%d, deleted=%d, skipped=%d, errors=%d, freed=%d bytes, empty_dirs_removed=%d',
    $scanned,$deleted,$skipped,$errors,$freed,$dirsRemoved
);
logLine("SUMMARY: {$summary}");
logSummary($summary);

flock($lockFp, LOCK_UN); fclose($lockFp);
exit($errors > 0 ? 1 : 0);
