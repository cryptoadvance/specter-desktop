{% include "includes/message_box.js" %}


/*  creating a notification from JS */
function createNotification(msg, timeout=3000, type="information", body=null, icon=null){
    url = "{{ url_for('wallets_endpoint_api.create_notification' ) }}";
	formData = new FormData();
	formData.append("title", msg)
	formData.append("timeout", timeout)
	formData.append("notification_type", type)
	formData.append("body", body)
	formData.append("icon", icon)
	send_request(url, 'POST', "{{ csrf_token() }}", formData)
}


function callback_notification_close(id){
    //console.log('closed message')
    url = "{{ url_for('wallets_endpoint_api.js_notification_close', notification_id='this_notification_id') }}";
    send_request(url.replace('this_notification_id', id), 'GET', "{{ csrf_token() }}")
}

  
function javascript_popup_message(js_notification){

    /* see https://notifications.spec.whatwg.org/#api
    {
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




async function get_new_notifications(){
    url = "{{ url_for('wallets_endpoint_api.get_new_notifications') }}"
    console.log(url)
    send_request(url, 'GET', "{{ csrf_token() }}")
        .then(function (js_notifications) {
            // do something with the response
            console.log(js_notifications)
            for (let i in js_notifications) {
                javascript_popup_message(js_notifications[i]);
            }

        });
};



async function run_scheduled(){ 
    //this code runs every interval  
  // createNotification('yes triggered notification')  // Triggering a nottification from JS works.
  get_new_notifications() ;
};



function test_notifications(){
    createNotification('debug title', timeout=4000,  type='debug', body='body\nbody', icon='/path/to/icon.png');
    createNotification('info title', timeout=4000, type='information',  body='body\nbody', icon='/path/to/icon.png');
    createNotification('warning title', timeout=4000, type='warning',  body='body\nbody', icon='/path/to/icon.png');
    createNotification('error title', timeout=4000, type='error',  body='body\nbody', icon='/path/to/icon.png');
}

setInterval(run_scheduled, 2000);






