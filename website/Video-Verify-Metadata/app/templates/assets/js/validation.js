  // General validation for text fields
  document.querySelectorAll('input[type="text"], textarea').forEach(function(input) {
    input.addEventListener("input", function () {
      const errorElement = document.getElementById(input.id + "Error");
      if (input.validity.valid) {
        errorElement.classList.add("d-none");
      } else {
        errorElement.classList.remove("d-none");
      }
    });
  });

  // Credit line, Description, Instructions can be left as simple text fields without a strict pattern.
  document.querySelectorAll('input[type="text"], textarea').forEach(function(input) {
    input.addEventListener('input', function() {
      this.setCustomValidity('');
    });
  });

  const postalInput = document.getElementById("creatorPostalCode");
  const postalError = document.getElementById("postalCodeError");

  // Handle form submission
  document.querySelector("form").addEventListener("submit", function (e) {
    const value = postalInput.value.trim();
    if (!/^\d+$/.test(value)) {
      e.preventDefault();
      postalError.classList.remove("d-none");
    } else {
      postalError.classList.add("d-none");
    }
  });

  // Hide error when correcting input
  postalInput.addEventListener("input", function () {
    if (/^\d+$/.test(postalInput.value.trim())) {
      postalError.classList.add("d-none");
    }
  });

  const allowEmailChars = (event) => {
    const char = String.fromCharCode(event.which);
    if (!/[a-zA-Z0-9@._-]/.test(char)) {
      event.preventDefault();
    }
  };

  const emailInput = document.getElementById("creatorEmail");
  const emailError = document.getElementById("emailError");

  if (emailInput) {
    emailInput.addEventListener("keypress", allowEmailChars);

    emailInput.addEventListener("input", () => {
      if (emailInput.validity.valid && emailError) {
        emailError.classList.add("d-none");
      }
    });
  }

  function showEmailError() {
    if (emailError) {
      emailError.classList.remove("d-none");
    }
  }

  
  const phoneInput = document.getElementById("creatorPhone");
  const phoneError = document.getElementById("phoneError");

  document.querySelector("form").addEventListener("submit", function (e) {
    const value = phoneInput.value.trim();
    const isValid = /^\d{10}$/.test(value);

    if (!isValid) {
      e.preventDefault();
      phoneError.classList.remove("d-none");
    } else {
      phoneError.classList.add("d-none");
    }
  });

  phoneInput.addEventListener("input", function () {
    const value = phoneInput.value.trim();
    if (/^\d{10}$/.test(value)) {
      phoneError.classList.add("d-none");
    }
  });

  const urlInput = document.getElementById("creatorWebUrl");
  const urlError = document.getElementById("urlError");

  document.querySelector("form").addEventListener("submit", function (e) {
    const value = urlInput.value.trim();
    const isValid = /https?:\/\/(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}(?:\/[\w.-]*)*/.test(value);

    if (!isValid) {
      e.preventDefault();
      urlError.classList.remove("d-none");
    } else {
      urlError.classList.add("d-none");
    }
  });

  urlInput.addEventListener("input", function () {
    const value = urlInput.value.trim();
    if (/https?:\/\/(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}(?:\/[\w.-]*)*/.test(value)) {
      urlError.classList.add("d-none");
    }
  });