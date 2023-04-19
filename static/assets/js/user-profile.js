const options = {
    debug: 'info',
    modules: {
        toolbar: '#toolbar-container'
    },
    theme: 'snow'
};
const editor = new Quill('#editor-container',options);

document.querySelector('#edit-btn').addEventListener('click', (e) => {
    document.querySelector('#bio').classList.add('d-none');
    document.querySelector('#bio-content').classList.add('d-none');
    document.querySelector('.quill-container').classList.remove('d-none');
    document.querySelector('#save-container').classList.remove('d-none');
})

// Edit user details
document.querySelector('#ProfileUpdateBtn').addEventListener('click' , (e) => {

    var formData = new FormData($("#ProfileUpdateForm")[0]);

    $.ajax({
        type: "POST",
        url: "/profile",
        data: formData,
        async: false,
        cache: false,
        contentType: false,
        processData: false,
        success: function (res) {
            // success message
            success_msg(res.message)
            setTimeout(function(){
                location.reload();
        },1000);
        },
        error: function (request, error) {
            // error message
            error_msg(JSON.parse(request.responseText)['message'])          
        }
});
} )
// end edit user details

// Edit user bio
document.querySelector('#edit-bio').addEventListener('click' , (e) => {

    const data = []
    document.querySelector('.ql-editor').childNodes.forEach((node) => {
        data.push(node.outerHTML)
    })

    var formData = new FormData($("#edit-bio")[0]);
    formData.append('bio', data.join(''));

    $.ajax({
        type: "POST",
        url: "/edit_bio",
        data: formData,
        async: false,
        cache: false,
        contentType: false,
        processData: false,
        success: function (res) {
            setTimeout(function(){
                location.reload();
        },500);
        },
        error: function (request, error) {
            const message = document.querySelector('#alert')
            message.textContent = JSON.parse(request.responseText)['error']
            message.classList.add('text-danger')
            message.classList.remove('text-success')
        }
});
} )
// end edit user bio

// delete user
$(document).on("click", "#delete-account", function(e){
    e.preventDefault();
   
    Swal.fire({
            title:"Do you want delete this item?",
            type: "warning",
            showCancelButton: true,
            confirmButtonClass: 'btn btn-success',
            cancelButtonClass: 'btn btn-danger',
            buttonsStyling: false,
            confirmButtonText: "Delete",
            cancelButtonText: "Cancel",
            closeOnConfirm: false,
            showLoaderOnConfirm: true,
            }).then((isConfirm) => {

                if(isConfirm.value == true){
                    $.ajax({
                        type: "DELETE",
                        url: "/delete_user",
                        dataType: 'json',
                        success: function(res){
                            window.location.replace('/');
                        },
                        error: function (request, error) {
                            // error message
                            error_msg(JSON.parse(request.responseText)['message'])
                        }
                    });
                    }
                return false;
            });
    });
// end delete user

// success message funcation
function success_msg(res){
    const message = document.querySelector('#alert')
    message.textContent = res
    message.classList.add('text-success')
    message.classList.remove('text-danger')
}
// error message funcation
function error_msg(res){
    const message = document.querySelector('#alert')
    message.textContent = res
    message.classList.add('text-danger')
    message.classList.remove('text-success')
}
// end 

