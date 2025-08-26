// Array to keep track of filenames
const uploadedFilenames = [];

// Function to populate the form with default values
function populateDefaultValues() {
    const defaultValues = {
        creatorName: 'John Doe',
        creatorAddress: '123 Main St',
        creatorCity: 'Anytown',
        creatorState: 'CA',
        creatorCountry: 'USA',
        creatorPostalCode: '12345',
        creatorEmail: 'johndoe@example.com',
        creatorPhone: '555-1234',
        creatorWebUrl: 'http://example.com',
        creatorsJobtitle: 'Photographer',
        creditLine: 'John Doe Photography',
        dateCreated: '2024-08-30',
        copyrightNotice: '© 2024 John Doe',
        rightsUsageTerms: 'All rights reserved',
        description: 'A beautiful sunset over the mountains.',
        descriptionWriter: 'John Doe',
        headline: 'Sunset Over Mountains',
        instructions: 'Handle with care',
        keywords: 'sunset, mountains, nature',
        title: 'Sunset Over Mountains',
        aiTraining: 'notAllowed',
        aiGenerativeTraining: 'notAllowed',
        dataMining: 'notAllowed',
        aiInference: 'notAllowed'
    };

    // Populate the form fields with default values
    Object.keys(defaultValues).forEach(field => {
        const inputElement = document.getElementById(`${field}Input`);
        if (inputElement) {
            inputElement.value = defaultValues[field];
        } else {
            const selectElement = document.getElementById(field);
            if (selectElement) {
                selectElement.value = defaultValues[field];
            }
        }
    });
}

// Attach event listener to the "Default Values" button
document.getElementById('defaultValuesButton').addEventListener('click', populateDefaultValues);

document.getElementById('uploadForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent the default form submission

    const formData = new FormData();

    // List of form fields to be included in the form data
    const fields = [
        'creatorName', 'creatorAddress', 'creatorCity', 'creatorState', 'creatorCountry',
        'creatorPostalCode', 'creatorEmail', 'creatorPhone', 'creatorWebUrl', 'creatorsJobtitle',
        'creditLine', 'dateCreated', 'copyrightNotice', 'rightsUsageTerms', 'description',
        'descriptionWriter', 'headline', 'instructions', 'keywords', 'title',
        'aiTraining', 'aiGenerativeTraining', 'dataMining', 'aiInference',
        'aiTrainingConstraintInfo', 'aiGenerativeTrainingConstraintInfo', 'dataMiningConstraintInfo', 'aiInferenceConstraintInfo'
    ];

    // Append form fields to the FormData object
    fields.forEach(field => {
        const inputElement = document.getElementById(`${field}Input`);
        if (inputElement) {
            formData.append(field, inputElement.value || '');
        }
    });

    // Append the file to the FormData object
    const fileInput = document.getElementById('fileInput');
    let filename = '';
    if (fileInput && fileInput.files.length > 0) {
        const file = fileInput.files[0];
        formData.append('file', file);
        filename = file.name;
    }

    // Show the loading signifier
    const loadingElement = document.getElementById('loading');
    loadingElement.style.display = 'block';

    fetch('/upload', {
        method: 'POST',
        body: formData,
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        // Simulate a delay to test the loading indicator
        setTimeout(() => {
            const resultElement = document.getElementById('result');

            // Check if the filename already exists in the array
            if (uploadedFilenames.includes(filename)) {
                // Remove the existing link
                const existingLinks = resultElement.querySelectorAll('a');
                existingLinks.forEach(link => {
                    if (link.textContent.includes(filename)) {
                        link.nextElementSibling.remove(); // Remove the <br> element
                        link.remove(); // Remove the link
                    }
                });
            }

            // Add the new filename to the array
            uploadedFilenames.push(filename);

            if (data.downloadLink) {
                const downloadLink = document.createElement('a');
                downloadLink.href = data.downloadLink;
                const timestamp = new Date().toLocaleString();
                downloadLink.textContent = `Download Processed File: ${filename} (${timestamp})`;
                downloadLink.target = '_blank'; // Open in a new tab
                resultElement.appendChild(downloadLink);
                resultElement.appendChild(document.createElement('br')); // Add a new paragraph
            } else {
                resultElement.textContent = 'No download link available.';
            }
            loadingElement.style.display = 'none';
        }, 0); // delay for testing color change
    })
    .catch(error => {
        console.error('Error:', error);
        const resultElement = document.getElementById('result');
        resultElement.textContent = 'Upload failed!';
        // Hide the loading signifier
        loadingElement.style.display = 'none';
    })
});