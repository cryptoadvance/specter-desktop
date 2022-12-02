const { src, dest, watch } = require('gulp');
const livereload = require('gulp-livereload');

const TEMPLATE_FOLDER = 'cryptoadvance/specter/templates'
const STATIC_FOLDER = 'cryptoadvance/specter/static'

const SRC_PREFIX = 'src/' 
const DESTINATION = '.env/lib/python3.10/site-packages/'

exports.default = function() {
  watch([`src/**/*.{jinja,html,css,svg}`], { events: 'all' }, (cb) => {
    console.log("Change in source folder")
    
    src(`src/cryptoadvance/specter/**/*.{jinja,html,css,svg}`)
      .pipe(dest(`.env/lib/python3.10/site-packages/cryptoadvance/specter/`))
      .pipe(livereload()) // trigger update

    cb();
  })
  
  // watch([`${SRC_PREFIX}${TEMPLATE_FOLDER}/**/*.{jinja,html}`], { events: 'all' }, (cb) => {
  //   console.log('Template: Copying files to', `${DESTINATION}${TEMPLATE_FOLDER}`)
    
  //   src(`${SRC_PREFIX}${TEMPLATE_FOLDER}/**/*.{jinja,html}`)
  //     .pipe(dest(`${DESTINATION}${TEMPLATE_FOLDER}`))
  //     .pipe(livereload()) // trigger update

  //   cb();
  // })

  // watch([`${SRC_PREFIX}${STATIC_FOLDER}/**/*.{css,svg}`], { events: 'all' }, (cb) => {
  //   console.log('Static: Copying files to', `${DESTINATION}${TEMPLATE_FOLDER}`)

  //   src(`${SRC_PREFIX}${STATIC_FOLDER}/*.{css,svg}`)
  //     .pipe(dest(`${DESTINATION}${STATIC_FOLDER}/**/*.{css,svg}`))
  //     .pipe(livereload()) // trigger update

  //   cb();
  // })

  // start live reload
  livereload.listen({ port: 35729 })
}
