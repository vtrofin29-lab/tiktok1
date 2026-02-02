#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Verificare PyTorch pentru RTX 5070
Acest script verifică dacă PyTorch este instalat corect pentru RTX 5070 (Blackwell)
"""

import sys
import subprocess

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def check_python():
    """Check Python version and location"""
    print_section("1. VERIFICARE PYTHON")
    print(f"Versiune: {sys.version}")
    print(f"Locație: {sys.executable}")
    
    # Check if Python is 3.8+
    if sys.version_info < (3, 8):
        print("⚠️  AVERTISMENT: Python 3.8+ este recomandat pentru PyTorch modern")
    else:
        print("✅ Versiune Python OK")

def check_pytorch():
    """Check PyTorch installation"""
    print_section("2. VERIFICARE PYTORCH")
    
    try:
        import torch
        version = torch.__version__
        print(f"Versiune: {version}")
        
        # Check if version is adequate
        if '+cu' in version:
            if '+cu121' in version or '+cu124' in version:
                print("✅ PyTorch instalat cu CUDA 12.x (corect pentru RTX 5070)")
            elif '+cu118' in version:
                print("⚠️  AVERTISMENT: CUDA 11.8 poate fi prea vechi pentru RTX 5070")
                print("   Recomandare: Reinstalează cu CUDA 12.1")
            else:
                print(f"✅ PyTorch cu CUDA detectat: {version}")
        elif '+cpu' in version:
            print("❌ PROBLEMĂ: PyTorch CPU-only detectat!")
            print("   PyTorch nu va folosi GPU-ul!")
            print("\n   SOLUȚIE:")
            print("   pip uninstall torch torchvision torchaudio -y")
            print("   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
            return False
        else:
            print(f"Versiune PyTorch: {version}")
        
        # Check PyTorch version number
        try:
            version_parts = version.split('+')[0].split('.')
            major = int(version_parts[0])
            minor = int(version_parts[1])
            
            if major > 2 or (major == 2 and minor >= 2):
                print("✅ Versiune PyTorch adecvată pentru RTX 5070")
            else:
                print(f"⚠️  AVERTISMENT: PyTorch {major}.{minor} poate fi prea vechi pentru RTX 5070")
                print("   RTX 5070 necesită PyTorch 2.2.0+")
        except:
            pass
        
        return True
        
    except ImportError:
        print("❌ PROBLEMĂ CRITICĂ: PyTorch NU este instalat!")
        print("\n   SOLUȚIE:")
        print("   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
        return False

def check_cuda():
    """Check CUDA availability"""
    print_section("3. VERIFICARE CUDA")
    
    try:
        import torch
        
        is_available = torch.cuda.is_available()
        print(f"CUDA disponibil: {is_available}")
        
        if is_available:
            print("✅ CUDA este disponibil în PyTorch")
            return True
        else:
            print("❌ PROBLEMĂ: CUDA nu este disponibil!")
            print("\n   Posibile cauze:")
            print("   1. PyTorch CPU-only instalat (verifică versiunea mai sus)")
            print("   2. Drivere NVIDIA lipsă sau invalide")
            print("   3. CUDA toolkit incompatibil")
            print("\n   Verifică:")
            print("   - nvidia-smi funcționează?")
            print("   - PyTorch instalat cu CUDA (nu CPU-only)?")
            return False
            
    except ImportError:
        print("❌ PyTorch nu este instalat")
        return False

def check_gpu():
    """Check GPU detection"""
    print_section("4. VERIFICARE GPU")
    
    try:
        import torch
        
        if not torch.cuda.is_available():
            print("CUDA nu este disponibil - nu pot detecta GPU")
            return False
        
        # Get GPU name
        gpu_name = torch.cuda.get_device_name(0)
        print(f"GPU detectat: {gpu_name}")
        
        # Get compute capability
        capability = torch.cuda.get_device_capability(0)
        compute_cap = capability[0] + capability[1] / 10
        print(f"Compute capability: {compute_cap} (sm_{capability[0]}{capability[1]})")
        
        # Check if it's RTX 5070
        if 'RTX 5070' in gpu_name or 'RTX 50' in gpu_name:
            print("✅ RTX 5070 detectat corect!")
            if compute_cap >= 9.0:
                print("✅ Compute capability corespunzătoare pentru Blackwell")
            return True
        else:
            print(f"ℹ️  GPU detectat: {gpu_name}")
            print(f"   Compute capability: {compute_cap}")
        
        return True
        
    except Exception as e:
        print(f"❌ Eroare la detectarea GPU: {e}")
        return False

def check_architectures():
    """Check supported CUDA architectures - MOST IMPORTANT for RTX 5070"""
    print_section("5. VERIFICARE ARHITECTURI CUDA (CRUCIAL pentru RTX 5070!)")
    
    try:
        import torch
        
        if not torch.cuda.is_available():
            print("CUDA nu este disponibil - nu pot verifica arhitecturile")
            return False
        
        arch_list = torch.cuda.get_arch_list()
        print(f"Arhitecturi suportate: {arch_list}")
        
        # Check for sm_90 (Blackwell - RTX 50 series)
        has_sm90 = 'sm_90' in arch_list
        
        print("\nVerificare arhitecturi specifice:")
        important_archs = {
            'sm_75': 'Turing (RTX 20xx, GTX 16xx)',
            'sm_80': 'Ampere (RTX 30xx, A100)',
            'sm_86': 'Ampere (RTX 30xx)',
            'sm_89': 'Ada Lovelace (RTX 40xx)',
            'sm_90': 'Blackwell (RTX 50xx) - NECESAR pentru RTX 5070!'
        }
        
        for arch, description in important_archs.items():
            if arch in arch_list:
                marker = "✅" if arch != 'sm_90' else "✅✅✅"
                print(f"  {marker} {arch}: {description}")
            else:
                marker = "  " if arch != 'sm_90' else "❌❌❌"
                print(f"  {marker} {arch}: {description} - LIPSĂ")
        
        print()
        if has_sm90:
            print("=" * 70)
            print("✅✅✅ EXCELENT! PyTorch suportă RTX 5070!")
            print("=" * 70)
            print("sm_90 (Blackwell) găsit în arhitecturi")
            print("RTX 5070 va funcționa la viteză maximă!")
            return True
        else:
            print("=" * 70)
            print("❌❌❌ PROBLEMĂ CRITICĂ! PyTorch NU suportă RTX 5070!")
            print("=" * 70)
            print("sm_90 (Blackwell) LIPSEȘTE din arhitecturi!")
            print("\nAceasta este CAUZA erorii tale!")
            print("\n🔧 SOLUȚIE:")
            print("   1. Dezinstalează PyTorch actual:")
            print("      pip uninstall torch torchvision torchaudio -y")
            print("\n   2. Curăță cache:")
            print("      pip cache purge")
            print("\n   3. Instalează PyTorch cu suport RTX 5070:")
            print("      pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir")
            print("\n   4. Verifică din nou:")
            print("      python verifica_pytorch.py")
            print("\n   5. Repornește aplicația COMPLET")
            return False
        
    except Exception as e:
        print(f"❌ Eroare la verificarea arhitecturilor: {e}")
        return False

def check_nvidia_smi():
    """Check nvidia-smi"""
    print_section("6. VERIFICARE DRIVERE NVIDIA (nvidia-smi)")
    
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            print("✅ nvidia-smi funcționează")
            
            # Extract CUDA version
            for line in result.stdout.split('\n'):
                if 'CUDA Version' in line:
                    print(f"   {line.strip()}")
                    # Check CUDA version
                    if '12.' in line:
                        print("   ✅ CUDA 12.x detectat (bun pentru RTX 5070)")
                    elif '11.' in line:
                        print("   ⚠️  CUDA 11.x detectat (poate fi prea vechi pentru RTX 5070)")
                elif 'RTX 5070' in line or 'RTX 50' in line:
                    print(f"   ✅ GPU găsit: {line.strip()}")
            
            return True
        else:
            print("❌ nvidia-smi a returnat eroare")
            print(f"   Cod eroare: {result.returncode}")
            if result.stderr:
                print(f"   Mesaj: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ PROBLEMĂ: nvidia-smi nu este găsit!")
        print("\n   Aceasta înseamnă că driverele NVIDIA nu sunt instalate sau nu sunt în PATH")
        print("\n   SOLUȚIE:")
        print("   1. Descarcă drivere NVIDIA de pe:")
        print("      https://www.nvidia.com/Download/index.aspx")
        print("   2. Selectează: GeForce RTX 50 Series → RTX 5070")
        print("   3. Instalează driverele")
        print("   4. Repornește PC-ul")
        print("   5. Rulează din nou acest script")
        return False
    except subprocess.TimeoutExpired:
        print("⚠️  nvidia-smi timeout - driverele pot avea probleme")
        return False
    except Exception as e:
        print(f"❌ Eroare la rularea nvidia-smi: {e}")
        return False

def print_summary(results):
    """Print summary of all checks"""
    print_section("REZUMAT FINAL")
    
    all_ok = all(results.values())
    
    print("\nStare verificări:")
    for check, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {check}")
    
    print("\n" + "=" * 70)
    if all_ok:
        print("🎉 TOTUL ESTE OK! PyTorch este configurat corect pentru RTX 5070!")
        print("=" * 70)
        print("\n✅ Aplicația ar trebui să funcționeze pe GPU la viteză maximă!")
        print("✅ Repornește aplicația dacă nu ai făcut-o deja")
        print("\nPerformanță așteptată:")
        print("  • Video de 5 minute: ~7 minute procesare totală")
        print("  • Whisper transcription: 5-8 minute pe GPU")
    else:
        print("❌ PROBLEME DETECTATE - PyTorch nu este configurat corect")
        print("=" * 70)
        print("\n🔧 Urmează instrucțiunile de mai sus pentru a rezolva problemele")
        print("\nCei mai importanți pași:")
        print("  1. Asigură-te că sm_90 este în arhitecturi (verificarea #5)")
        print("  2. Asigură-te că CUDA este disponibil (verificarea #3)")
        print("  3. Asigură-te că nvidia-smi funcționează (verificarea #6)")

def main():
    """Main verification function"""
    print("=" * 70)
    print("   VERIFICARE PYTORCH PENTRU RTX 5070 (Blackwell)")
    print("=" * 70)
    print("\nAcest script verifică dacă PyTorch este instalat și configurat")
    print("corect pentru a folosi RTX 5070 la capacitate maximă.\n")
    
    results = {}
    
    # Run all checks
    check_python()
    results['PyTorch instalat'] = check_pytorch()
    results['CUDA disponibil'] = check_cuda()
    results['GPU detectat'] = check_gpu()
    results['sm_90 suportat'] = check_architectures()  # MOST IMPORTANT!
    results['nvidia-smi funcționează'] = check_nvidia_smi()
    
    # Print summary
    print_summary(results)
    
    # Exit code
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
