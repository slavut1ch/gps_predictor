<?php

header('Content-Type: application/json');

define('STORAGE', __DIR__ . '/storage');
define('SCRIPTS', __DIR__ . '/../scripts');

require_once(__DIR__ . '/../config.php');

if (!is_dir(STORAGE)) mkdir(STORAGE, 0755, true);

function safe($s)  { return preg_replace('/[^a-zA-Z0-9_\-]/','',$s); }     // prepares a string for safe use
function udir($u)  { return STORAGE.'/'.$u; }                              // user's storage directory
function out($d)   { echo json_encode($d, JSON_UNESCAPED_UNICODE); exit; } // sends a JSON response
function fail($m)  { http_response_code(400); out(['error'=>$m]); }        // responds with a 400 error status
function ncsv($u)  { return count(glob(udir($u).'/csvs/*.csv') ?: []); }   // the number of CSV's in the user's directory

$action = $_REQUEST['action'] ?? '';
$user   = safe($_REQUEST['user'] ?? '');

switch ($action) {

case 'login':
    if (!$user) fail('No name entered');
    $d = udir($user);
    if (!is_dir($d)) mkdir($d.'/csvs', 0755, true);
    out([
        'has_model' => file_exists($d.'/model.pt'),
        'csv_count' => ncsv($user),
        'min_csv'   => MIN_CSV]);
    break;

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
    
    $d = udir($user);
    
    $cmd = PY.' '.escapeshellarg(SCRIPTS . '/train.py')
         .' --csv_dir '.escapeshellarg("$d/csvs")
         .' --out '.escapeshellarg("$d/model.pt") . ' 2>&1';

    $output = shell_exec($cmd);
    
    file_put_contents("$d/train.log", $output);

    if (file_exists("$d/model.pt")) {
        out(['status' => 'done', 'log' => $output]);
    } else {
        fail("Training failed: " . $output);
    }
    break;

case 'predict':
    if (!$user || !is_dir(udir($user))) fail('no user');
    $d = udir($user);
    if (!file_exists("$d/model.pt")) fail('Model isn\'t trained');
    if (empty($_FILES['file']['tmp_name'])) fail('No CSV');

    $tmp = "$d/query.csv";
    if (!move_uploaded_file($_FILES['file']['tmp_name'], $tmp)) fail('upload fail');

    $cmd = PY . ' ' . escapeshellarg(SCRIPTS . '/predict.py') 
        . ' --csv ' . escapeshellarg($tmp) 
        . ' --model ' . escapeshellarg("$d/model.pt");
    $raw = (string)shell_exec($cmd . ' 2>&1');
    $pred = json_decode($raw, true);

    if (!$pred || !isset($pred['pred_angle'])) {
        @unlink($tmp);
        fail('predict error: '.trim($raw));
    }

    $res = $pred;
    if (($_POST['matching'] ?? '') === '1') {
        $cmd_match = PY . ' ' . escapeshellarg(SCRIPTS . '/matching.py')
            . ' --csv ' . escapeshellarg($tmp)
            . ' --angle ' . escapeshellarg((string)$pred['pred_angle']);
        $r2 = shell_exec($cmd_match . ' 2>&1');
        $m = json_decode((string)$r2, true);
        if ($m) $res['match'] = $m;
    }
    @unlink($tmp);
    out($res);

default: fail('unknown action');
}
