function webpush_notification(title, options) {
    function show_notification(){
        let notification = new Notification(title, options);
    };



    // Let's check if the browser supports notifications    
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
        });
    }

    // At last, if the user has denied notifications, and you
    // want to be respectful there is no need to bother them any more.
};


function webpush_tx(tx) {
    title = `Incoming Transaction`;
    amount = tx["amount"];
    amount_formatted = amount.toFixed(8);
    if  (amount>0){
        amount_formatted = `+${amount_formatted}`
    };

    var options = {
        body:   amount_formatted,
    };
    webpush_notification(title, options);
};

current_chaintip_height = -1
function evalaute_new_transactions(){
    fetch("{{ url_for('wallets_endpoint_api.get_updated_wallet_infos') }}")
        .then(function (response) {
            return response.json();
        }).then(function (wallets_txlists) {
            // do something with the response
            for (let i in wallets_txlists) {
                console.log(wallets_txlists[i])
                webpush_tx(wallets_txlists[i])
            }

        });
};

function notify_new_block(max_chaintip_height){
    //webpush_notification(`New Block ${max_chaintip_height}`)
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
                notify_new_block(max_chaintip_height)
                current_chaintip_height = max_chaintip_height;
                //console.log(`new Block!!!  ${max_chaintip_height}`);
                // location.reload();
            } ;
        console.log(max_chaintip_height);
        });

};


setInterval(run_scheduled, 2000);






