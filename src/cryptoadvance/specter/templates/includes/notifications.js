{% include "includes/message_box.js" %}


/*  creating a notification from JS */
async function requestCreateNotification(title=null, timeout=5000, type="information", target_uis=null, body=null, image=null, icon=null){
    url = "{{ url_for('wallets_endpoint_api.create_notification' ) }}";
	formData = new FormData();
	formData.append("title", title)
	formData.append("timeout", timeout)
	formData.append("notification_type", type)
	formData.append("target_uis", JSON.stringify(target_uis))
	formData.append("body", body)
	formData.append("image", image)
	formData.append("icon", icon)
    return send_request(url, 'POST', "{{ csrf_token() }}", formData)
}




function callback_notification_close(id){
    //console.log('closed message')
    requestCreateNotification('callback_notification_close', timeout=0,  type='debug', target_uis=['internal_notification'], body=JSON.stringify({'id':id}));
}


function notification_shown(id, success=true){
    //console.log('closed message')
    requestCreateNotification('notification_shown', timeout=0,  type='debug', target_uis=['internal_notification'], body=JSON.stringify({'id':id, 'success':success}));
}


function notification_webapi_notification_unavailable(id) {
    requestCreateNotification('webapi_notification_unavailable', timeout=0,  type='debug', target_uis=['internal_notification'], body=JSON.stringify({'id':id}));
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



function webapi_notification(js_notification, retries_if_permission_default=2) {
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
            notification_shown(js_notification['id'])
        });        

        function closeNotification(){notification.close()}
        if (js_notification['timeout']>0) {
            setTimeout(closeNotification, js_notification['timeout']);
        }
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
    // Otherwise  "default", we need to ask the user for permission
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
            if (retries_if_permission_default>0){
                // create recursion loop, that breaks if user grants or blocks the notification
                setTimeout(webapi_notification, 2000, js_notification, retries_if_permission_default=retries_if_permission_default-1);  
            }
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

    var message = js_notification['title'];
    if (js_notification['options']['body']) {
        message += '\n\n' + js_notification['options']['body']
    }

    msgbox = new MessageBox({
        closeTime: js_notification['timeout']
      });
    msgbox.show(
        message,
        callback_notification_close_id,
        'Close',
        image=js_notification['options']['image'],
        );			

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
    } else if (ui_name == 'js_console'){
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
  // requestCreateNotification('yes triggered notification')  // Triggering a nottification from JS works.
  get_new_notifications() ;
};



function test_notifications(){
    requestCreateNotification('title send to js_console and print', timeout=0,  type='debug', target_uis=['js_console', 'print'], body='body\nbody', icon='/path/to/icon.png');
    requestCreateNotification('title send to js_console and print', timeout=0,  type='warning', target_uis=['js_console', 'print'], body='body\nbody', icon='/path/to/icon.png');
    requestCreateNotification('info for js_message_box', timeout=0, type='information',  target_uis='js_message_box', body='body\nbody', icon='/path/to/icon.png');
    requestCreateNotification('info for WebAPI', timeout=0, type='information',  target_uis='WebAPI', body='body\nbody', icon='/path/to/icon.png');
    //requestCreateNotification('info for flask', timeout=0, type='information',  target_uis='flash', body='body\nbody', icon='/path/to/icon.png');
    //requestCreateNotification('warning title', timeout=0, type='warning', target_uis='all', body='body\nbody', icon='/path/to/icon.png');
    //requestCreateNotification('error title', timeout=0, type='error', target_uis='all', body='body\nbody', icon='/path/to/icon.png');
    get_new_notifications();
}

setInterval(run_scheduled, 2000);






