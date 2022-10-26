/** functions to include in a module to show errors **/
function showError(msg){
    let event = new CustomEvent('errormsg', { detail: { message: msg } });
    document.dispatchEvent(event);
}
function showNotification(msg){
    let event = new CustomEvent('notification', { detail: { message: msg } });
    document.dispatchEvent(event);
}