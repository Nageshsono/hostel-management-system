// ================================
// Hostel Management System
// script.js
// ================================

// Confirm before deleting a student
function confirmDelete() {
    return confirm("Are you sure you want to delete this student?");
}

// Auto hide flash messages after 3 seconds
window.onload = function () {

    let flash = document.getElementById("flash-message");

    if (flash) {
        setTimeout(function () {
            flash.style.display = "none";
        }, 3000);
    }

};

// Search students instantly
function searchStudent() {

    let input = document.getElementById("searchInput");

    if (input) {
        window.location.href = "/search?keyword=" + input.value;
    }

}