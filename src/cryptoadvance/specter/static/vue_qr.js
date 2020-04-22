/**
 * @brief This component splits a large qr (text) into smaller chunks.
 * E.g. a multisig PSBT is split into individual chunks with headers which
 * can be animated on a mouse click:
 *
 * ["p1of6 Multisig 5&wsh(sortedmulti(1,[f8720f8e/48h/1h/0h/2",
 * "p2of6 h]tpubDEwGuKMeWUefghYUSEvJkbzKN9hNLTWT56aCThafPMjY",
 * "p3of6 q2y9L7JQQSrNYx2FoTzFdzAtSHntnGNy4aeDjfLxJa7wKE5czu",
 * "p4of6 ExXWFzerNsiWo,[9d1dc604/48h/1h/0h/2h]tpubDEAMhNB9p",
 * "p5of6 UL6Ej2HuiJUU1TDMqHNxRKjGFxLfCB7cmxKjQKXNF4yR8CMpgD",
 * "p6of6 t5eh5V3XesKDUrcFHYDMz3u3ybWwHSAZZQLjiMAi4oKy6HEg))" ]
 *
 * param[in] text
 * param[in] width
*/
Vue.component('qrencode',{
  template : '<div :title="title" v-on:click="clicked()"><qrcode :value="qrval" \
              :options="wd"></qrcode><div class="note">{{title}}</div></div>',
  data: function() {
     return {
        speed : 300,
        indx : 0,
        qrval : "",
        chunks : [],
        title : "",
        isQRlarge : false,
        isQRplaying : false,
        isQRtoolarge : false,
        wd : { width: 400 }
     }
  },
  props: ['text', 'width'],
  created() {
    this.split()
    this.qrval=this.text
    this.wd = {width: this.width}
    if (this.isQRlarge && !this.isQRtoolarge) {this.title = "Click to animate!"}
  },
  mounted() {this.init()},
  methods:{
    split : function() {
      var max_len = 300
      txt_len = this.text.length
      if (txt_len / max_len > 1.0) {
        this.isQRlarge = true
        if (txt_len >= 2300) {this.isQRtoolarge = true}
        /* This algorithm makes all the chunks of about equal length.
        This makes sure that the last chunk is not (too) different in size
        which is visually noticeable when animation occurs */
        let number_of_chunks = Math.ceil(txt_len / max_len)
        n = Math.ceil(txt_len / number_of_chunks)
        for (let i = 0; i < txt_len; i += n) {
          this.chunks.push(this.text.substring(i, i + n));
        }
        for (let j=0; j<this.chunks.length; j++) {
          this.chunks[j] = "p"+(j+1)+"of"+number_of_chunks+" "+this.chunks[j]
        }
      }
      else {
        this.chunks.push(this.text)
      }
    },
    animate : function() {
      if (this.isQRtoolarge) {
        this.indx++
        if (this.indx >= this.chunks.length) {this.indx = 0}
        this.qrval = this.chunks[this.indx]
        return
      }
      if (this.isQRplaying == false) {
        this.qrval = this.text
        this.title = "Click to animate!"
      }
      else {
        this.indx++
        if (this.indx >= this.chunks.length) {this.indx = 0}
        this.qrval = this.chunks[this.indx]
        this.title = "Click to stop animation!"
      }
      if (!this.isQRlarge) {
        this.title = ""
      }
    },
    init : function() {
      const self=this
      setInterval(self.animate, this.speed)
    },
    clicked : function() {
      this.isQRplaying = !this.isQRplaying
    }
  }
});
