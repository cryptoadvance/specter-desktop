{% include "includes/message_box.js" %}


/*  creating a notification from JS */
function createNotification(msg, timeout=5000, type="information", target_uis=null, body=null, icon=null){
    url = "{{ url_for('wallets_endpoint_api.create_notification' ) }}";
	formData = new FormData();
	formData.append("title", msg)
	formData.append("timeout", timeout)
	formData.append("notification_type", type)
	formData.append("target_uis", JSON.stringify(target_uis))
	formData.append("body", body)
	formData.append("icon", icon)
	formData.append("image", icon)
	send_request(url, 'POST', "{{ csrf_token() }}", formData)
}




function callback_notification_close(id){
    //console.log('closed message')
    createNotification('callback_notification_close', timeout=0,  type='debug', target_uis=['internal_notification'], body=JSON.stringify({'id':id}));
}


function notification_shown(id, success=true){
    //console.log('closed message')
    createNotification('notification_shown', timeout=0,  type='debug', target_uis=['internal_notification'], body=JSON.stringify({'id':id, 'success':success}));
}


function notification_webapi_notification_unavailable(id) {
    createNotification('webapi_notification_unavailable', timeout=0,  type='debug', target_uis=['internal_notification'], body=JSON.stringify({'id':id}));
}


    /* js_notification structure see https://notifications.spec.whatwg.org/#api
    options : {  
        "//": "Visual Options",
        "body": "<String>",
        "icon": "<URL String>",
        "image": "<URL String>",
        "badge": "<URL String>",
        "vibrate": "<Array of Integers>",
        "sound": "<URL String>",
        "dir": "<String of 'auto' | 'ltr' | 'rtl'>",
    
        "//": "Behavioral Options",
        "tag": "<String>",
        "data": "<Anything>",
        "requireInteraction": "<boolean>",
        "renotify": "<Boolean>",
        "silent": "<Boolean>",
    
        "//": "Both visual & behavioral options",
        "actions": "<Array of Strings>",
    
        "//": "Information Option. No visual affect.",
        "timestamp": "<Long>"
    }
    */

function webapi_notification(js_notification) {
    console.log('webapi_notification')
    // https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
    var title = js_notification['title'];
    var options = js_notification['options'];

    function create_webapi_notification(){
        let notification = new Notification(title, options);
        // see https://flaviocopes.com/notifications-api/#add-an-image
        // see https://levelup.gitconnected.com/use-the-javascript-notification-api-to-display-native-popups-43f6227b9980
        // see https://www.htmlgoodies.com/html5/creating-your-own-notifications-with-the-html5-notifications-api/
        notification.onclick = (() => {
            // do something
        });        
        notification.onclose = (() => {
            callback_notification_close(js_notification['id'])
        });        
        notification.onshow = (() => {
            // do something
        });        
        if (js_notification['timeout']>0) {
            setTimeout(notification.close(), js_notification['timeout']);
        }
        notification_shown(js_notification['id'])
    };


    if (!("Notification" in window)) {
        console.log("This browser does not support desktop notification");
        notification_webapi_notification_unavailable(js_notification['id']);
    }
    // Let's check whether notification permissions have already been granted
    else if (Notification.permission === "granted") {
        // If it's okay let's create a notification
        create_webapi_notification();
    }  else if (Notification.permission === "denied") {
        // If it's okay let's create a notification
        console.log(`Notification.requestPermission() = ${Notification.permission}`);
        notification_webapi_notification_unavailable(js_notification['id']);  
    }
    // Otherwise, we need to ask the user for permission
    else   {
        Notification.requestPermission().then(function (permission) {
        // If the user accepts, let's create a notification
        if (permission === "granted") {
            create_webapi_notification();
        } else if (permission === "denied") {
            // not granted
            console.log(`Notification.requestPermission() = ${permission}`);
            notification_webapi_notification_unavailable(js_notification['id']);  
        } else {
            // permission is probably "default", meaning the user has neither granted nor blocked the Notifications.
            // The user can afterwards allow or block notifications.  The notification needs reboradcasting.
            console.log(`Notification.requestPermission() = ${permission}`);

            // create endless recursion loop, that only breaks if user grants or blocks the notification
            setTimeout(webapi_notification, 5000, js_notification);  
        }
        });
    }


    

      
    // At last, if the user has denied notifications, and you
    // want to be respectful there is no need to bother them any more.
};




  
function javascript_popup_message(js_notification){


    function callback_notification_close_id(){
        callback_notification_close(js_notification['id'])    
    }

    const closeLabel = 'Close';
    msgboxPersistent.show(
        `${js_notification['title']}\n\n${js_notification['options']['body']}`,
        //() => {
        //  console.log("I am the callback! Of course, you may add various javaScript codes to make the callback function colourful.");
        //},
        callback_notification_close_id,
        closeLabel);			

    notification_shown(js_notification['id'])
}


function js_logging_notification(js_notification){
    if (js_notification['type'] == 'error'){
        console.error(js_notification)
    } else if (js_notification['type'] == 'exception'){
        console.error(js_notification)
    } else if (js_notification['type'] == 'warning'){
        console.warn(js_notification)
    } else {            
        console.log(js_notification);
    }
    notification_shown(js_notification['id'])
}

async function show_notification(ui_name, js_notification){
    if (ui_name == 'js_message_box'){
        javascript_popup_message(js_notification);
    } else if (ui_name == 'WebAPI'){
        webapi_notification(js_notification);
    } else if (ui_name == 'js_logging'){
        js_logging_notification(js_notification);
    }

}


async function get_new_notifications(){
    url = "{{ url_for('wallets_endpoint_api.get_new_notifications') }}"
    //console.log(url)


    function myFunction(item) {
        sum += item;
    }

    send_request(url, 'GET', "{{ csrf_token() }}").then(function (js_notifications_dict) {
            //console.log(js_notifications_dict);
            for (var ui_name in js_notifications_dict) {
            //console.log("obj." + ui_name + " = " + js_notifications_dict[ui_name]);
            for (let i in js_notifications_dict[ui_name]) {  
                show_notification(ui_name, js_notifications_dict[ui_name][i])  ;   
            }            
        }        
    });
}



async function run_scheduled(){ 
    //this code runs every interval  
  // createNotification('yes triggered notification')  // Triggering a nottification from JS works.
  get_new_notifications() ;
};



function test_notifications(){
    createNotification('title send to js_logging and print', timeout=0,  type='debug', target_uis=['js_logging', 'print'], body='body\nbody', icon='/path/to/icon.png');
    createNotification('title send to js_logging and print', timeout=0,  type='warning', target_uis=['js_logging', 'print'], body='body\nbody', icon='/path/to/icon.png');
    createNotification('info for js_message_box', timeout=0, type='information',  target_uis='js_message_box', body='body\nbody', icon='/path/to/icon.png');
    createNotification('info for WebAPI', timeout=0, type='information',  target_uis='WebAPI', body='body\nbody', icon='/path/to/icon.png');
    //createNotification('info for flask', timeout=0, type='information',  target_uis='flash', body='body\nbody', icon='/path/to/icon.png');
    //createNotification('warning title', timeout=0, type='warning', target_uis='all', body='body\nbody', icon='/path/to/icon.png');
    //createNotification('error title', timeout=0, type='error', target_uis='all', body='body\nbody', icon='/path/to/icon.png');
    get_new_notifications();
}

setInterval(run_scheduled, 2000);






