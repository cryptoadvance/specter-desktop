const { src, dest, watch } = require('gulp');
const livereload = require('gulp-livereload');

const TEMPLATE_FOLDER = 'cryptoadvance/specter/templates'
const STATIC_FOLDER = 'cryptoadvance/specter/static'

const SRC_PREFIX = 'src/' 
const DESTINATION = '.env/lib/python3.10/site-packages/'

exports.default = function() {
  watch([`src/**/*.{jinja,html,css,svg}`], { events: 'all' }, (cb) => {
    if (process.argv.includes('--site-packages')) {
      console.log('Running gulp livereload and copying files to site-packages.')
      src(`src/cryptoadvance/**/*.{jinja,html,css,svg}`)
      .pipe(dest(`.env/lib/python3.10/site-packages/cryptoadvance/`))
      .pipe(livereload())
    }
    else {
      console.log('Running gulp livereload.')
      src(`src/cryptoadvance/**/*.{jinja,html,css,svg}`)
      .pipe(livereload())
   }
    cb();
  })
  // start live reload
  livereload.listen({ port: 35729 })
}
