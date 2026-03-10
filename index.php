<?php
header('Content-Type: application/json');

define('STORAGE', __DIR__ . '/storage');
define('PY',      'python');
define('MIN_CSV', 50);

if (!is_dir(STORAGE)) mkdir(STORAGE, 0755, true);

function safe($s)  { return preg_replace('/[^a-zA-Z0-9_\-]/','',$s); }
function udir($u)  { return STORAGE.'/'.$u; }
function out($d)   { echo json_encode($d, JSON_UNESCAPED_UNICODE); exit; }
function fail($m)  { http_response_code(400); out(['error'=>$m]); }
function ncsv($u)  { return count(glob(udir($u).'/csvs/*.csv') ?: []); }

function pid_alive($pid) {
    if ($pid <= 1) return false;
    $o = shell_exec("tasklist /FI \"PID eq $pid\" /NH 2>NUL");
    return $o && str_contains($o, (string)$pid);
}

$action = $_REQUEST['action'] ?? '';
$user   = safe($_REQUEST['user'] ?? '');

switch ($action) {

case 'login':
    if (!$user) fail('No name entered');
    $d = udir($user);
    if (!is_dir($d)) mkdir($d.'/csvs', 0755, true);
    out(['has_model' => file_exists($d.'/model.pt'), 'csv_count' => ncsv($user)]);

case 'upload':
    if (!$user || !is_dir(udir($user))) fail('no user');
    $dest = udir($user).'/csvs';
    $ok = $fail = 0;
    foreach ((array)($_FILES['files']['name'] ?? []) as $i => $name) {
        $tmp  = $_FILES['files']['tmp_name'][$i] ?? '';
        $safe = preg_replace('/[^a-zA-Z0-9_\-\.]/', '_', basename($name));
        if ($tmp && move_uploaded_file($tmp, "$dest/$safe")) $ok++; else $fail++;
    }
    out(['ok' => $ok, 'fail' => $fail, 'total' => ncsv($user)]);

case 'train':
    if (!$user || !is_dir(udir($user))) fail('no user');
    $n = ncsv($user);
    if ($n < MIN_CSV) fail("Needed minimum ".MIN_CSV." CSV (now: $n)");
    $d   = udir($user);
    $pid_f = "$d/train.pid";
    $log_f = "$d/train.log";
    if (file_exists($pid_f)) {
        $pid = (int)file_get_contents($pid_f);
        if (pid_alive($pid)) out(['status'=>'already_running']);
        unlink($pid_f);
    }
    file_put_contents($log_f, '');
    $cmd = PY.' '.escapeshellarg(__DIR__.'/train.py')
         .' --csv_dir '.escapeshellarg("$d/csvs")
         .' --out '.escapeshellarg("$d/model.pt");
    $bat = sys_get_temp_dir().'/gps_train.bat';
    file_put_contents($bat, "@echo off\r\n$cmd > ".escapeshellarg($log_f)." 2>&1\r\n");
    pclose(popen("start /B cmd /C ".escapeshellarg($bat), 'r'));
    sleep(1);
    $w = shell_exec('wmic process where "name=\'python.exe\'" get processid /format:value 2>NUL');
    preg_match_all('/ProcessId=(\d+)/', $w ?: '', $m);
    $pid = isset($m[1]) ? (int)end($m[1]) : 1;
    file_put_contents($pid_f, $pid ?: 1);
    out(['status' => 'started']);

case 'train_status':
    if (!$user || !is_dir(udir($user))) fail('no user');
    $d      = udir($user);
    $pid_f  = "$d/train.pid";
    $log_f  = "$d/train.log";
    $has    = file_exists("$d/model.pt");
    $log    = '';
    if (file_exists($log_f)) {
        $lines = file($log_f) ?: [];
        $log   = implode('', array_slice($lines, -25));
    }
    if (!file_exists($pid_f)) out(['status' => $has ? 'done' : 'idle', 'has_model'=>$has, 'log'=>$log]);
    $pid  = (int)file_get_contents($pid_f);
    $alive = pid_alive($pid);
    $has   = file_exists("$d/model.pt");
    if (!$alive && $pid !== 1) { unlink($pid_f); out(['status'=>$has?'done':'error','has_model'=>$has,'log'=>$log]); }
    if (!$alive && $has)       { unlink($pid_f); out(['status'=>'done','has_model'=>true,'log'=>$log]); }
    out(['status'=>'running','has_model'=>$has,'log'=>$log]);

case 'predict':
    if (!$user || !is_dir(udir($user))) fail('no user');
    $d = udir($user);
    if (!file_exists("$d/model.pt")) fail('Model isn\'t trained');
    if (empty($_FILES['file']['tmp_name'])) fail('No CSV');
    $tmp = "$d/query.csv";
    if (!move_uploaded_file($_FILES['file']['tmp_name'], $tmp)) fail('upload fail');
    $cd  = 'cd /D '.escapeshellarg($d);
    $raw = (string)shell_exec($cd.' && '.PY.' '.escapeshellarg(__DIR__.'/predict.py').' '.escapeshellarg($tmp).' 2>&1');
    $pred = json_decode($raw, true);
    if (!$pred || !isset($pred['pred_angle'])) { @unlink($tmp); fail('predict error: '.trim($raw)); }
    $res = $pred;
    if (($_POST['matching'] ?? '') === '1') {
        $r2 = shell_exec(PY.' '.escapeshellarg(__DIR__.'/matching.py')
            .' --csv_file '.escapeshellarg($tmp)
            .' --angle '.escapeshellarg((string)$pred['pred_angle'])
            .' 2>&1');
        $m = json_decode((string)$r2, true);
        if ($m) $res['match'] = $m;
    }
    @unlink($tmp);
    out($res);

default: fail('unknown action');
}