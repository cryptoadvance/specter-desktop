
function webpush_notification(text) {
    // Let's check if the browser supports notifications
    if (!("Notification" in window)) {
        console.debug("This browser does not support desktop notification");
    }
    // Let's check whether notification permissions have already been granted
    else if (Notification.permission === "granted") {
        // If it's okay let's create a notification
        let notification = new Notification(text);
    }

    // Otherwise, we need to ask the user for permission
    else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(function (permission) {
        // If the user accepts, let's create a notification
        if (permission === "granted") {
            let notification = new Notification(text);
        }
        });
    }

    // At last, if the user has denied notifications, and you
    // want to be respectful there is no need to bother them any more.
    }



current_chaintip_height = -1
function evalaute_new_transactions(){
    fetch("{{ url_for('wallets_endpoint_api.get_updated_wallet_infos') }}")
        .then(function (response) {
            return response.json();
        }).then(function (wallets_txlists) {
            // do something with the response
            for (let i in wallets_txlists) {
                console.log(wallets_txlists[i])
                webpush_notification(`New Transaction ${wallets_txlists[i]["amount"]}`)
            }

        });
};

function run_scheduled(){ 
    //this code runs every interval
    fetch("{{ url_for('wallets_endpoint_api.get_max_chaintip_height') }}")
        .then(function (response) {
            return response.json();
        }).then(function (max_chaintip_height) {
            // do something with the response
            if (current_chaintip_height == -1){
                current_chaintip_height = max_chaintip_height;
            }
            if (current_chaintip_height != max_chaintip_height){
                evalaute_new_transactions()
                current_chaintip_height = max_chaintip_height;
                webpush_notification(`New Block ${max_chaintip_height}`)
                //console.log(`new Block!!!  ${max_chaintip_height}`);
                // location.reload();
            } ;
        console.log(max_chaintip_height);
        });

};


setInterval(run_scheduled, 2000);

