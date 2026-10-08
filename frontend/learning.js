function copyCode(btn) {
    const code = btn.nextElementSibling.innerText;

    navigator.clipboard.writeText(code);

    btn.innerText = "Copied!";
    setTimeout(() => {
        btn.innerText = "Copy";
    }, 1500);
}