document.addEventListener("DOMContentLoaded", function () {
  function setBodyWrapperHeight() {
    var bodyWrapper = document.querySelector('.body-wrapper');
    if (bodyWrapper) {
      var topOffset = bodyWrapper.getBoundingClientRect().top;
      var windowHeight = window.innerHeight;
      bodyWrapper.style.height = (windowHeight - topOffset) + 'px';
    }
  }

  // Set height on load
  setBodyWrapperHeight();

  // Adjust height on window resize
  window.addEventListener('resize', setBodyWrapperHeight);
});