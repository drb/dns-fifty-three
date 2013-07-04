<?
/**
 * Simple web service to return the client IP in a JSON object
 */

header('Content-Type: application/json');
$ip = $_SERVER['REMOTE_ADDR'];
$payload = array("client_ip"=>$ip);
print (json_encode($payload));
?>