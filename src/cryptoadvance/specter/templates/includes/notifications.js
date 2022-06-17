{% include "includes/message_box.js" %}


/*  creating a notification from JS */
function createNotification(msg, timeout=3000, type="information", target_uis='all', body=null, icon=null){
    url = "{{ url_for('wallets_endpoint_api.create_notification' ) }}";
	formData = new FormData();
	formData.append("title", msg)
	formData.append("timeout", timeout)
	formData.append("notification_type", type)
	formData.append("target_uis", JSON.stringify(target_uis))
	formData.append("body", body)
	formData.append("icon", icon)
	send_request(url, 'POST', "{{ csrf_token() }}", formData)
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

function webpush_notification(js_notification) {
    // https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API
    var title = js_notification['title'];
    var options = js_notification['options'];

    function show_notification(){
        let notification = new Notification(title, options);
    };


        if (!("Notification" in window)) {
        console.debug("This browser does not support desktop notification");
    }
    // Let's check whether notification permissions have already been granted
    else if (Notification.permission === "granted") {
        // If it's okay let's create a notification
        show_notification();
    }
    // Otherwise, we need to ask the user for permission
    else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(function (permission) {
        // If the user accepts, let's create a notification
        if (permission === "granted") {
            show_notification();
        }        
        else{
         // not granted
        }
        });
    }


    

      
    // At last, if the user has denied notifications, and you
    // want to be respectful there is no need to bother them any more.
};




function callback_notification_close(id){
    //console.log('closed message')
    url = "{{ url_for('wallets_endpoint_api.js_notification_close', notification_id='this_notification_id') }}";
    send_request(url.replace('this_notification_id', id), 'GET', "{{ csrf_token() }}")
}

  
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
}




async function show_notification(ui_name, js_notification){
    if (ui_name == 'js_message_box'){
        javascript_popup_message(js_notification);
    } else if (ui_name == 'WebAPI'){
        webpush_notification(js_notification);
    } else if (ui_name == 'js_logging'){
        console.log(js_notification);
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
    createNotification('info for js_message_box', timeout=0, type='information',  target_uis='js_message_box', body='body\nbody', icon='/path/to/icon.png');
    createNotification('info for WebAPI', timeout=0, type='information',  target_uis='WebAPI', body='body\nbody', icon='/path/to/icon.png');
    // createNotification('info for flask', timeout=0, type='information',  target_uis='flask', body='body\nbody', icon='/path/to/icon.png');
    //createNotification('warning title', timeout=0, type='warning', target_uis='all', body='body\nbody', icon='/path/to/icon.png');
    //createNotification('error title', timeout=0, type='error', target_uis='all', body='body\nbody', icon='/path/to/icon.png');
    get_new_notifications();
}

setInterval(run_scheduled, 2000);






